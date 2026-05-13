"""Asynchronous AI cover generation task service."""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_processor.image_generator import generate_cover_for_article
from config import OPENAI_IMAGE_MODEL
from database import get_db, is_mysql

logger = logging.getLogger(__name__)


class CoverTaskService:
    """Queue and execute AI cover generation without blocking web requests."""

    @staticmethod
    def create_cover_task(article_id: int, style: str = "") -> dict[str, Any] | None:
        conn = get_db()
        try:
            article = CoverTaskService._select_article(conn, article_id)
            if not article:
                return None

            existing = CoverTaskService._select_active_task(conn, article_id)
            if existing:
                return dict(existing)

            prompt = (article["cover_prompt"] or "").strip() if "cover_prompt" in article.keys() else ""
            if is_mysql():
                cursor = conn.execute(
                    """
                    INSERT INTO cover_generation_tasks
                    (article_id, status, task_type, model, prompt, style)
                    VALUES (%s, 'queued', 'article_cover', %s, %s, %s)
                    """,
                    (article_id, OPENAI_IMAGE_MODEL, prompt, style),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO cover_generation_tasks
                    (article_id, status, task_type, model, prompt, style)
                    VALUES (?, 'queued', 'article_cover', ?, ?, ?)
                    """,
                    (article_id, OPENAI_IMAGE_MODEL, prompt, style),
                )
            task_id = cursor.lastrowid
            conn.commit()
            task = CoverTaskService.get_cover_task(task_id)
            logger.info("[cover-task] created article_id=%s task_id=%s", article_id, task_id)
            return task
        finally:
            conn.close()

    @staticmethod
    def get_cover_task(task_id: int) -> dict[str, Any] | None:
        conn = get_db()
        try:
            if is_mysql():
                row = conn.execute("SELECT * FROM cover_generation_tasks WHERE id=%s", (task_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM cover_generation_tasks WHERE id=?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_latest_cover_task(article_id: int) -> dict[str, Any] | None:
        conn = get_db()
        try:
            if is_mysql():
                row = conn.execute(
                    "SELECT * FROM cover_generation_tasks WHERE article_id=%s ORDER BY id DESC LIMIT 1",
                    (article_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM cover_generation_tasks WHERE article_id=? ORDER BY id DESC LIMIT 1",
                    (article_id,),
                ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def execute_cover_task(task_id: int) -> dict[str, Any]:
        conn = get_db()
        try:
            task = CoverTaskService._select_task(conn, task_id)
            if not task:
                return {"ok": False, "msg": "cover task not found"}
            if task["status"] != "queued":
                return {"ok": True, "msg": "cover task already finished", "task": dict(task)}

            claim_cursor = CoverTaskService._mark_running(conn, task_id)
            if getattr(claim_cursor, "rowcount", 0) <= 0:
                conn.rollback()
                logger.info("[cover-task] skipped task_id=%s because it was already claimed", task_id)
                return {"ok": True, "msg": "cover task already claimed", "task_id": task_id}
            conn.commit()
            logger.info("[cover-task] running article_id=%s task_id=%s", task["article_id"], task_id)

            article = CoverTaskService._select_article(conn, task["article_id"])
            if not article:
                CoverTaskService._mark_failed(conn, task_id, task["article_id"], "article not found")
                conn.commit()
                return {"ok": False, "msg": "article not found"}

            try:
                cover_payload = generate_cover_for_article(dict(article), style=task["style"] or "")
                cover_status = cover_payload.get("cover_status", "failed")
                if cover_status == "success":
                    CoverTaskService._update_article_cover(conn, task["article_id"], cover_payload)
                    CoverTaskService._mark_success(conn, task_id, cover_payload)
                    conn.commit()
                    logger.info("[cover-task] success article_id=%s task_id=%s", task["article_id"], task_id)
                    return {"ok": True, "task_id": task_id, "cover_status": cover_status}

                error_message = cover_payload.get("cover_error") or "cover generation failed"
                CoverTaskService._update_article_failed(conn, task["article_id"])
                CoverTaskService._mark_failed(conn, task_id, task["article_id"], error_message)
                conn.commit()
                logger.warning(
                    "[cover-task] failed article_id=%s task_id=%s error=%s",
                    task["article_id"],
                    task_id,
                    error_message,
                )
                return {"ok": False, "task_id": task_id, "error_message": error_message}
            except Exception as exc:
                CoverTaskService._update_article_failed(conn, task["article_id"])
                CoverTaskService._mark_failed(conn, task_id, task["article_id"], str(exc))
                conn.commit()
                logger.exception(
                    "[cover-task] failed article_id=%s task_id=%s error=%s",
                    task["article_id"],
                    task_id,
                    exc,
                )
                return {"ok": False, "task_id": task_id, "error_message": str(exc)}
        finally:
            conn.close()

    @staticmethod
    def run_pending_cover_tasks(limit: int = 3) -> int:
        safe_limit = max(1, min(int(limit or 3), 20))
        conn = get_db()
        try:
            if is_mysql():
                rows = conn.execute(
                    "SELECT id FROM cover_generation_tasks WHERE status='queued' ORDER BY id ASC LIMIT %s",
                    (safe_limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM cover_generation_tasks WHERE status='queued' ORDER BY id ASC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
            task_ids = [row["id"] for row in rows]
        finally:
            conn.close()

        for task_id in task_ids:
            CoverTaskService.execute_cover_task(task_id)
        return len(task_ids)

    @staticmethod
    def _select_article(conn, article_id: int):
        if is_mysql():
            return conn.execute("SELECT * FROM articles WHERE id=%s", (article_id,)).fetchone()
        return conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()

    @staticmethod
    def _select_task(conn, task_id: int):
        if is_mysql():
            return conn.execute("SELECT * FROM cover_generation_tasks WHERE id=%s", (task_id,)).fetchone()
        return conn.execute("SELECT * FROM cover_generation_tasks WHERE id=?", (task_id,)).fetchone()

    @staticmethod
    def _select_active_task(conn, article_id: int):
        if is_mysql():
            return conn.execute(
                """
                SELECT * FROM cover_generation_tasks
                WHERE article_id=%s AND status IN ('queued', 'running')
                ORDER BY id DESC LIMIT 1
                """,
                (article_id,),
            ).fetchone()
        return conn.execute(
            """
            SELECT * FROM cover_generation_tasks
            WHERE article_id=? AND status IN ('queued', 'running')
            ORDER BY id DESC LIMIT 1
            """,
            (article_id,),
        ).fetchone()

    @staticmethod
    def _mark_running(conn, task_id: int):
        if is_mysql():
            return conn.execute(
                """
                UPDATE cover_generation_tasks
                SET status='running', updated_at=CURRENT_TIMESTAMP, started_at=CURRENT_TIMESTAMP
                WHERE id=%s AND status='queued'
                """,
                (task_id,),
            )
        return conn.execute(
            """
            UPDATE cover_generation_tasks
            SET status='running', updated_at=datetime('now','localtime'), started_at=datetime('now','localtime')
            WHERE id=? AND status='queued'
            """,
            (task_id,),
        )

    @staticmethod
    def _mark_success(conn, task_id: int, payload: dict[str, Any]) -> None:
        result_payload = json.dumps(payload, ensure_ascii=False)
        if is_mysql():
            conn.execute(
                """
                UPDATE cover_generation_tasks
                SET status='success', result_payload=%s, error_message='',
                    updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (result_payload, task_id),
            )
        else:
            conn.execute(
                """
                UPDATE cover_generation_tasks
                SET status='success', result_payload=?, error_message='',
                    updated_at=datetime('now','localtime'), finished_at=datetime('now','localtime')
                WHERE id=?
                """,
                (result_payload, task_id),
            )

    @staticmethod
    def _mark_failed(conn, task_id: int, article_id: int, error_message: str) -> None:
        if is_mysql():
            conn.execute(
                """
                UPDATE cover_generation_tasks
                SET status='failed', error_message=%s, retry_count=retry_count+1,
                    updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (error_message, task_id),
            )
        else:
            conn.execute(
                """
                UPDATE cover_generation_tasks
                SET status='failed', error_message=?, retry_count=retry_count+1,
                    updated_at=datetime('now','localtime'), finished_at=datetime('now','localtime')
                WHERE id=?
                """,
                (error_message, task_id),
            )
        logger.warning("[cover-task] failed article_id=%s task_id=%s error=%s", article_id, task_id, error_message)

    @staticmethod
    def _update_article_cover(conn, article_id: int, payload: dict[str, Any]) -> None:
        params = (
            payload.get("cover_image", ""),
            payload.get("cover_url", ""),
            payload.get("cover_status", "success"),
            payload.get("cover_prompt", ""),
            article_id,
        )
        if is_mysql():
            conn.execute(
                """
                UPDATE articles
                SET cover_image=%s, cover_url=%s, cover_status=%s, cover_prompt=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                params,
            )
        else:
            conn.execute(
                """
                UPDATE articles
                SET cover_image=?, cover_url=?, cover_status=?, cover_prompt=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                params,
            )

    @staticmethod
    def _update_article_failed(conn, article_id: int) -> None:
        if is_mysql():
            conn.execute(
                "UPDATE articles SET cover_status='failed', updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                (article_id,),
            )
        else:
            conn.execute(
                "UPDATE articles SET cover_status='failed', updated_at=datetime('now','localtime') WHERE id=?",
                (article_id,),
            )


create_cover_task = CoverTaskService.create_cover_task
get_cover_task = CoverTaskService.get_cover_task
get_latest_cover_task = CoverTaskService.get_latest_cover_task
execute_cover_task = CoverTaskService.execute_cover_task
run_pending_cover_tasks = CoverTaskService.run_pending_cover_tasks
