"""模板文章生成服务。"""

import traceback
import logging

from ai_processor.content_writer import write_with_template
from ai_processor.image_generator import generate_cover_for_article
from ai_processor.processor import format_original_article
from config import OPENAI_BASE_URL, OPENAI_MODEL
from database import get_db, get_existing_columns, init_default_templates, is_mysql
from domain.article_status import STATUS_DRAFT, split_legacy_status
from services.wechat_lead_card_adapter import append_lead_qr_at_end
from services.title_guard import TitleGuard

logger = logging.getLogger(__name__)


class TemplateService:
    """封装模板生成文章的业务逻辑。"""

    @staticmethod
    def ensure_default_templates() -> None:
        """确保六大默认写作模板存在，便于老数据库自动补齐。"""
        init_default_templates()

    @staticmethod
    def _select_template_by_id(conn, tmpl_id: int):
        """按主键查询模板，显式区分两端占位符。"""
        if is_mysql():
            return conn.execute(
                "SELECT * FROM article_templates WHERE id=%s",
                (tmpl_id,),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM article_templates WHERE id=?",
            (tmpl_id,),
        ).fetchone()

    @staticmethod
    def _select_article_id_by_title(conn, title: str):
        """按标题查重，显式区分两端占位符。"""
        if is_mysql():
            return conn.execute(
                "SELECT id FROM articles WHERE title=%s",
                (title,),
            ).fetchone()
        return conn.execute(
            "SELECT id FROM articles WHERE title=?",
            (title,),
        ).fetchone()

    @staticmethod
    def _insert_generated_article(db, article: dict, topic: str, review_status: str, publish_status: str):
        """将模板生成文章写入数据库，并同步保存封面信息。"""
        raw_title = article.get("title", topic)
        candidate_titles = article.get("title_candidates") or []
        if article.get("final_title"):
            candidate_titles = [article.get("final_title"), *list(candidate_titles)]
        guarded_title = TitleGuard.sanitize_title(
            raw_title,
            candidates=candidate_titles,
            keyword=topic,
        )["title"]
        content = TitleGuard.ensure_title_in_text(article.get("content", ""), raw_title, guarded_title)
        html_content = TitleGuard.ensure_title_in_html(article.get("html_content", ""), raw_title, guarded_title)

        params = (
            guarded_title,
            content,
            article.get("summary", ""),
            article.get("cover_url", ""),
            article.get("cover_image", ""),
            article.get("cover_status", "pending"),
            article.get("cover_prompt", ""),
            article.get("source_name", "沪上银号原创"),
            article.get("source_url", ""),
            article.get("tags", f"{topic},原创"),
            STATUS_DRAFT,
            review_status,
            publish_status,
            1,
            append_lead_qr_at_end(html_content),
        )
        if is_mysql():
            cursor = db.execute(
                """
                INSERT INTO articles
                (title, content, summary, cover_url, cover_image, cover_status, cover_prompt, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                params,
            )
            return cursor.lastrowid

        cursor = db.execute(
            """
            INSERT INTO articles
            (title, content, summary, cover_url, cover_image, cover_status, cover_prompt, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            params,
        )
        return cursor.lastrowid

    @staticmethod
    def create_agent_article(article: dict, keyword: str) -> dict:
        """写入 ArticleGenerationAgent 生成的草稿，并返回文章 ID。"""
        db = get_db()
        try:
            review_status, publish_status = split_legacy_status(STATUS_DRAFT)
            article_id = TemplateService._insert_generated_article(
                db,
                {
                    "title": article.get("title", keyword),
                    "content": article.get("markdown", ""),
                    "summary": article.get("summary", ""),
                    "cover_prompt": article.get("cover_prompt", ""),
                    "source_name": "沪上银原创",
                    "source_url": "",
                    "tags": ",".join(article.get("tags", [])) if isinstance(article.get("tags"), list) else article.get("tags", ""),
                    "html_content": article.get("html", ""),
                    "title_candidates": article.get("title_candidates", []),
                    "final_title": article.get("final_title", ""),
                },
                keyword,
                review_status,
                publish_status,
            )
            columns = get_existing_columns(db, "articles")
            source_title = str(article.get("source_title") or keyword)
            generated_title = str(db.execute("SELECT title FROM articles WHERE id=%s" if is_mysql() else "SELECT title FROM articles WHERE id=?", (article_id,)).fetchone()[0])
            if {"source_title", "generated_title"}.issubset(columns):
                db.execute("UPDATE articles SET source_title=%s, generated_title=%s WHERE id=%s" if is_mysql() else "UPDATE articles SET source_title=?, generated_title=? WHERE id=?", (source_title, generated_title, article_id))
            db.commit()
            return {"ok": True, "article_id": article_id, "source_title": source_title, "generated_title": generated_title}
        finally:
            db.close()

    @staticmethod
    def create_agent_article_with_cover(article: dict, keyword: str) -> dict:
        """保存 Agent 草稿，并把 AI 封面生成交给后台任务处理。"""
        article_payload = {
            "title": article.get("title", keyword),
            "content": article.get("markdown", ""),
            "summary": article.get("summary", ""),
            "cover_prompt": article.get("cover_prompt", ""),
            "cover_status": "queued",
            "source_name": "沪上银原创",
            "source_url": "",
            "tags": ",".join(article.get("tags", [])) if isinstance(article.get("tags"), list) else article.get("tags", ""),
            "html_content": article.get("html", ""),
            "title_candidates": article.get("title_candidates", []),
            "final_title": article.get("final_title", ""),
        }

        db = get_db()
        try:
            review_status, publish_status = split_legacy_status(STATUS_DRAFT)
            article_id = TemplateService._insert_generated_article(
                db,
                article_payload,
                keyword,
                review_status,
                publish_status,
            )
            db.commit()
        finally:
            db.close()

        task = None
        cover_error = ""
        try:
            from services.cover_task_service import CoverTaskService

            task = CoverTaskService.create_cover_task(
                article_id,
                style=article.get("category", "") or article.get("category_key", "") or article_payload.get("tags", ""),
            )
        except Exception as exc:
            cover_error = str(exc)
            # 封面任务不能影响文章生成主流程；后台可稍后手动重新生成。
            traceback.print_exc()

        return {
            "ok": True,
            "article_id": article_id,
            "cover_status": task.get("status", "queued") if task else "pending",
            "cover_task_id": task.get("id") if task else None,
            "cover_image": "",
            "cover_error": cover_error,
        }

    @staticmethod
    def use_template(tmpl_id: int, topic: str, requested_template_key: str = "") -> dict:
        """根据模板生成文章并写入数据库。"""
        logger.info(
            "[template-write-start] template_id=%s topic=%s model=%s base_url=%s",
            tmpl_id, topic, OPENAI_MODEL, OPENAI_BASE_URL,
        )
        if not topic:
            return {"ok": False, "success": False, "status": "failed", "error_type": "MISSING_TOPIC", "error_message": "请输入话题关键词"}

        conn = get_db()
        try:
            tmpl = TemplateService._select_template_by_id(conn, tmpl_id)
        finally:
            conn.close()

        if not tmpl:
            return {"ok": False, "success": False, "status": "failed", "error_type": "TEMPLATE_NOT_FOUND", "error_message": "模板不存在"}

        if not tmpl["is_active"]:
            return {"ok": False, "success": False, "status": "failed", "error_type": "TEMPLATE_DISABLED", "error_message": "该模板已禁用，请启用后再使用"}

        template = dict(tmpl)
        resolved_template_key = str(requested_template_key or template.get("category") or "").strip()
        if resolved_template_key and resolved_template_key != str(template.get("category") or "").strip():
            return {"ok": False, "success": False, "status": "failed", "error_type": "TEMPLATE_MISMATCH", "error_message": "请求模板与已选模板不一致"}
        logger.info("[one-click-write-resolved] resolved_template_key=%s resolved_topic=%s", resolved_template_key, topic)
        try:
            article = write_with_template(topic=topic, template=template)
        except Exception as exc:
            logger.exception("[template-write-error] template_id=%s error_type=%s error=%s", tmpl_id, type(exc).__name__, exc)
            return {"ok": False, "success": False, "status": "failed", "error_type": type(exc).__name__, "error_message": str(exc) or "文章生成失败"}
        if not article:
            return {"ok": False, "success": False, "status": "failed", "error_type": "GENERATION_FAILED", "error_message": "文章生成失败，请检查AI配置或网络"}

        try:
            article = format_original_article(article)
        except Exception:
            traceback.print_exc()

        # 正文先落库；封面属于后处理，失败不得影响文章创建。
        article.update({"cover_url": "", "cover_image": "", "cover_status": "pending"})

        db = get_db()
        try:
            title = article.get("title", "").strip()
            existing = TemplateService._select_article_id_by_title(db, title)
            if existing:
                return {"ok": True, "success": True, "status": "success", "article_id": existing, "article_url": f"/article/{existing}", "source_title": topic, "generated_title": title, "article_type": resolved_template_key, "fallback_used": False, "message": "该话题文章已存在，请前往文章列表查看"}

            review_status, publish_status = split_legacy_status(STATUS_DRAFT)
            article_id = TemplateService._insert_generated_article(
                db, article, topic, review_status, publish_status,
            )
            db.commit()

            try:
                cover_payload = generate_cover_for_article(
                    article,
                    style=template.get("category_label", "") or template.get("category", ""),
                )
                placeholder = "%s" if is_mysql() else "?"
                db.execute(
                    f"UPDATE articles SET cover_url={placeholder}, cover_image={placeholder}, "
                    f"cover_status={placeholder}, cover_prompt={placeholder} WHERE id={placeholder}",
                    (
                        cover_payload.get("cover_url", ""),
                        cover_payload.get("cover_image", ""),
                        cover_payload.get("cover_status", "failed"),
                        cover_payload.get("cover_prompt", ""),
                        article_id,
                    ),
                )
                db.commit()
            except Exception as exc:
                logger.warning(
                    "[Cover-warning] article_id=%s 封面后处理失败，正文已保存: %s",
                    article_id,
                    exc,
                )
            fallback_used = bool(article.get("fallback_used"))
            logger.info("[one-click-write-success] article_id=%s source_title=%s generated_title=%s fallback_used=%s", article_id, topic, title, fallback_used)
            return {"ok": True, "success": True, "status": "success", "article_id": article_id, "article_url": f"/article/{article_id}", "source_title": topic, "generated_title": title, "article_type": resolved_template_key, "fallback_used": fallback_used, "message": "AI 不可用，已使用本地模板生成草稿" if fallback_used else "文章生成成功"}
        finally:
            db.close()
