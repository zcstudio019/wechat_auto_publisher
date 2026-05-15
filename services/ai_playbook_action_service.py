"""AI Ops Playbook 安全动作执行服务。

本服务只允许人工触发的只读动作：重新终检、重新运营决策。
严禁在这里修改文章、审核、发布、重试任务或创建发布任务。
"""
from __future__ import annotations

import logging
from typing import Any

from database import get_db, is_mysql
from services.article_decision_agent import ArticleDecisionAgent
from services.article_preflight_agent import ArticlePreflightAgent
from services.publish_task_service import PublishTaskService

logger = logging.getLogger(__name__)


class AIPlaybookActionService:
    """执行 Playbook 中人工确认后的安全动作。"""

    ALLOWED_ACTIONS = {"rerun_preflight", "rerun_decision"}

    @staticmethod
    def execute_action(action_type: str, article_id: int) -> dict[str, Any]:
        """执行白名单 Playbook 动作，返回 JSON 友好的结果。"""
        safe_action_type = (action_type or "").strip()
        if safe_action_type not in AIPlaybookActionService.ALLOWED_ACTIONS:
            return {"ok": False, "msg": "不支持的 Playbook 动作"}

        try:
            safe_article_id = int(article_id or 0)
        except (TypeError, ValueError):
            return {"ok": False, "msg": "文章 ID 无效"}

        if safe_article_id <= 0:
            return {"ok": False, "msg": "文章 ID 无效"}

        try:
            article = AIPlaybookActionService._get_article(safe_article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}

            if safe_action_type == "rerun_preflight":
                return AIPlaybookActionService._rerun_preflight(article)

            if safe_action_type == "rerun_decision":
                return AIPlaybookActionService._rerun_decision(article)

            return {"ok": False, "msg": "不支持的 Playbook 动作"}
        except Exception as exc:
            logger.warning(
                "[ai-playbook-action] action failed action_type=%s article_id=%s error=%s",
                safe_action_type,
                safe_article_id,
                exc,
            )
            return {"ok": False, "msg": f"Playbook 动作执行失败：{exc}"}

    @staticmethod
    def _get_article(article_id: int) -> dict[str, Any] | None:
        conn = get_db()
        try:
            placeholder = "%s" if is_mysql() else "?"
            article = conn.execute(
                f"SELECT * FROM articles WHERE id={placeholder}",
                (article_id,),
            ).fetchone()
            return dict(article) if article else None
        finally:
            conn.close()

    @staticmethod
    def _rerun_preflight(article: dict[str, Any]) -> dict[str, Any]:
        article_id = int(article.get("id") or 0)
        result = ArticlePreflightAgent().preflight_article(article)
        return {
            "ok": True,
            "action_type": "rerun_preflight",
            "article_id": article_id,
            "result": result,
        }

    @staticmethod
    def _rerun_decision(article: dict[str, Any]) -> dict[str, Any]:
        article_id = int(article.get("id") or 0)
        latest_task = PublishTaskService.get_latest_task_for_article(article_id)
        result = ArticleDecisionAgent().decide_next_action(
            article,
            review_result=None,
            preflight_result=None,
            latest_publish_task=latest_task,
        )
        return {
            "ok": True,
            "action_type": "rerun_decision",
            "article_id": article_id,
            "result": result,
        }
