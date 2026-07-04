"""
文章服务。

当前只承载文章内容类的安全写回能力，不处理审核、发布和任务调度。
"""
from __future__ import annotations

import re
from typing import Any

from database import get_db, is_mysql


class ArticleService:
    """文章内容服务。"""

    UNSAFE_WECHAT_TAGS = ("script", "style", "iframe", "form", "input", "textarea", "select")

    @staticmethod
    def apply_ai_rewrite(article_id: int, rewrite_payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """手动应用 AI 优化稿，只写回内容字段，不改变审核/发布状态。"""
        validation_error = ArticleService._validate_ai_rewrite_payload(rewrite_payload)
        if validation_error:
            return {"ok": False, "msg": validation_error}, 400

        title = ArticleService._safe_text(rewrite_payload.get("rewritten_title"))
        summary = ArticleService._safe_text(rewrite_payload.get("rewritten_summary"))
        content = ArticleService._safe_text(rewrite_payload.get("rewritten_content"))
        html_content = append_lead_qr_at_end(ArticleService._safe_text(rewrite_payload.get("rewritten_html_content")))

        conn = get_db()
        try:
            placeholder = "%s" if is_mysql() else "?"
            article = conn.execute(f"SELECT id FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404

            if is_mysql():
                conn.execute(
                    """
                    UPDATE articles
                    SET title=%s, summary=%s, content=%s, html_content=%s, updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s
                    """,
                    (title, summary, content, html_content, article_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE articles
                    SET title=?, summary=?, content=?, html_content=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (title, summary, content, html_content, article_id),
                )
            conn.commit()
            return {"ok": True, "msg": "已应用 AI 优化稿"}, 200
        except Exception as exc:
            conn.rollback()
            return {"ok": False, "msg": f"应用 AI 优化稿失败：{exc}"}, 500
        finally:
            conn.close()

    @staticmethod
    def _validate_ai_rewrite_payload(rewrite_payload: dict[str, Any]) -> str:
        """校验 AI 优化稿，避免写入空标题或公众号不兼容标签。"""
        if not isinstance(rewrite_payload, dict):
            return "优化稿数据格式不正确"

        title = ArticleService._safe_text(rewrite_payload.get("rewritten_title"))
        content = ArticleService._safe_text(rewrite_payload.get("rewritten_content"))
        html_content = append_lead_qr_at_end(ArticleService._safe_text(rewrite_payload.get("rewritten_html_content")))

        if not title:
            return "优化稿标题不能为空"
        if len(title) > 40:
            return "优化稿标题不能超过 40 字"
        if not (content or html_content):
            return "优化稿正文不能为空"
        if ArticleService._contains_unsafe_wechat_tag(html_content):
            return "优化稿包含不兼容标签，请重新生成"
        return ""

    @staticmethod
    def _contains_unsafe_wechat_tag(html_content: str) -> bool:
        """检查公众号正文中不应写入的真实交互/脚本标签。"""
        if not html_content:
            return False
        unsafe_pattern = r"<\s*(?:{})\b".format("|".join(ArticleService.UNSAFE_WECHAT_TAGS))
        return re.search(unsafe_pattern, html_content, flags=re.IGNORECASE) is not None

    @staticmethod
    def _safe_text(value: Any) -> str:
        """安全转字符串，避免 None 写入数据库。"""
        return str(value or "").strip()
