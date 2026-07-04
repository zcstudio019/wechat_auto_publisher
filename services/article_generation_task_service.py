"""Async-style task wrapper for article generation."""
from __future__ import annotations

import json
import logging
from typing import Any

from database import get_db, get_lastrowid, init_content_growth_tables
from services.article_generation_agent import ArticleGenerationAgent
from services.template_service import TemplateService

logger = logging.getLogger(__name__)

TASK_STATUS_QUEUED = "queued"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"


class ArticleGenerationTaskService:
    """Create, run, and inspect article generation tasks."""

    @staticmethod
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        init_content_growth_tables()
        safe_payload = ArticleGenerationTaskService._normalize_payload(payload)
        keyword = safe_payload.get("keyword", "")
        topic = safe_payload.get("topic", "") or keyword
        conn = get_db()
        try:
            cursor = conn.execute(
                """
                INSERT INTO article_generation_tasks
                (keyword, topic, payload_json, status, fallback_used)
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    keyword,
                    topic,
                    json.dumps(safe_payload, ensure_ascii=False),
                    TASK_STATUS_QUEUED,
                ),
            )
            task_id = get_lastrowid(cursor)
            conn.commit()
            return {"ok": True, "task_id": task_id, "status": TASK_STATUS_QUEUED}
        finally:
            conn.close()

    @staticmethod
    def run_task(task_id: int) -> dict[str, Any]:
        task = ArticleGenerationTaskService.get_task(task_id)
        if not task:
            return {"ok": False, "status": TASK_STATUS_FAILED, "error_message": "任务不存在"}
        if task.get("status") == TASK_STATUS_SUCCESS:
            return ArticleGenerationTaskService.format_task_response(task)
        if task.get("status") == TASK_STATUS_RUNNING:
            return ArticleGenerationTaskService.format_task_response(task)

        ArticleGenerationTaskService._mark_running(task_id)
        payload = ArticleGenerationTaskService._decode_payload(task.get("payload_json"))
        keyword = payload.get("keyword") or task.get("keyword") or task.get("topic") or "企业融资获客选题"
        fallback_used = False
        ai_error_message = ""

        try:
            generation_payload = ArticleGenerationTaskService._build_generation_payload(payload, keyword)
            result = ArticleGenerationAgent().generate(**generation_payload) or {}
            if not result.get("ok"):
                fallback_used = True
                ai_error_message = str(
                    result.get("error_message")
                    or result.get("msg")
                    or "AI 不可用，已使用本地模板生成草稿，请人工审核"
                )
                logger.warning(
                    "[article-generation-task-fallback] task_id=%s keyword=%s error_type=%s error=%s",
                    task_id,
                    keyword,
                    result.get("error_type") or "AI_PROVIDER_ERROR",
                    ai_error_message,
                )
                result = ArticleGenerationAgent.build_local_fallback(keyword, payload)

            saved = TemplateService.create_agent_article_with_cover(result, keyword) or {}
            article_id = saved.get("article_id")
            if not article_id:
                raise RuntimeError(saved.get("msg") or "文章草稿保存失败")

            success_message = ""
            if fallback_used:
                success_message = "AI 不可用，已使用本地模板生成草稿，请人工审核"
            ArticleGenerationTaskService._mark_success(task_id, article_id, fallback_used, success_message)
            return ArticleGenerationTaskService.get_task_status(task_id)
        except Exception as exc:
            logger.exception("[article-generation-task-error] task_id=%s error=%s", task_id, exc)
            if not fallback_used:
                try:
                    fallback = ArticleGenerationAgent.build_local_fallback(keyword, payload)
                    saved = TemplateService.create_agent_article_with_cover(fallback, keyword) or {}
                    article_id = saved.get("article_id")
                    if article_id:
                        ArticleGenerationTaskService._mark_success(
                            task_id,
                            article_id,
                            True,
                            "AI 不可用，已使用本地模板生成草稿，请人工审核",
                        )
                        return ArticleGenerationTaskService.get_task_status(task_id)
                except Exception as fallback_exc:
                    logger.exception(
                        "[article-generation-task-fallback-error] task_id=%s error=%s",
                        task_id,
                        fallback_exc,
                    )
                    ai_error_message = str(fallback_exc)
            ArticleGenerationTaskService._mark_failed(task_id, ai_error_message or str(exc) or "文章生成失败")
            return ArticleGenerationTaskService.get_task_status(task_id)

    @staticmethod
    def get_task_status(task_id: int) -> dict[str, Any]:
        task = ArticleGenerationTaskService.get_task(task_id)
        if not task:
            return {"ok": False, "status": TASK_STATUS_FAILED, "error_message": "任务不存在"}
        return ArticleGenerationTaskService.format_task_response(task)

    @staticmethod
    def get_task(task_id: int) -> dict[str, Any] | None:
        init_content_growth_tables()
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM article_generation_tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def format_task_response(task: dict[str, Any]) -> dict[str, Any]:
        article_id = task.get("article_id")
        return {
            "ok": True,
            "task_id": task.get("id"),
            "status": task.get("status") or TASK_STATUS_QUEUED,
            "article_id": article_id or "",
            "article_url": f"/article/{article_id}" if article_id else "",
            "fallback_used": bool(task.get("fallback_used")),
            "error_message": task.get("error_message") or "",
        }

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        keyword = str(payload.get("keyword") or payload.get("topic") or "").strip()
        secondary_raw = payload.get("secondary_categories") or []
        if isinstance(secondary_raw, str):
            secondary_categories = [item.strip() for item in secondary_raw.split(",") if item.strip()]
        elif isinstance(secondary_raw, list):
            secondary_categories = [str(item).strip() for item in secondary_raw if str(item).strip()]
        else:
            secondary_categories = []
        return {
            "keyword": keyword,
            "topic": str(payload.get("topic") or keyword).strip(),
            "primary_category": str(payload.get("primary_category") or payload.get("category") or "").strip(),
            "secondary_categories": secondary_categories,
            "length": str(payload.get("length") or "medium").strip() or "medium",
            "tone": str(payload.get("tone") or "").strip(),
            "audience": str(payload.get("audience") or "").strip(),
        }

    @staticmethod
    def _decode_payload(raw_payload: Any) -> dict[str, Any]:
        if isinstance(raw_payload, dict):
            return raw_payload
        try:
            data = json.loads(raw_payload or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _build_generation_payload(payload: dict[str, Any], keyword: str) -> dict[str, Any]:
        primary_category = payload.get("primary_category") or payload.get("category") or ""
        secondary_categories = payload.get("secondary_categories") or []
        return {
            "keyword": keyword,
            "primary_category": primary_category or "知识科普",
            "secondary_categories": secondary_categories if isinstance(secondary_categories, list) else [],
            "audience": payload.get("audience") or "企业老板 / 小微企业主",
            "tone": payload.get("tone") or "专业、可信、接地气、适合助贷/企业融资顾问行业",
            "length": payload.get("length") or "medium",
        }

    @staticmethod
    def _mark_running(task_id: int) -> None:
        ArticleGenerationTaskService._execute_update(
            """
            UPDATE article_generation_tasks
            SET status=?, started_at=datetime('now','localtime'), error_message=''
            WHERE id=?
            """,
            (TASK_STATUS_RUNNING, task_id),
        )

    @staticmethod
    def _mark_success(task_id: int, article_id: int, fallback_used: bool, message: str = "") -> None:
        ArticleGenerationTaskService._execute_update(
            """
            UPDATE article_generation_tasks
            SET status=?, article_id=?, fallback_used=?, error_message=?, finished_at=datetime('now','localtime')
            WHERE id=?
            """,
            (TASK_STATUS_SUCCESS, article_id, 1 if fallback_used else 0, message, task_id),
        )

    @staticmethod
    def _mark_failed(task_id: int, error_message: str) -> None:
        ArticleGenerationTaskService._execute_update(
            """
            UPDATE article_generation_tasks
            SET status=?, error_message=?, finished_at=datetime('now','localtime')
            WHERE id=?
            """,
            (TASK_STATUS_FAILED, error_message, task_id),
        )

    @staticmethod
    def _execute_update(sql: str, params: tuple[Any, ...]) -> None:
        conn = get_db()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()