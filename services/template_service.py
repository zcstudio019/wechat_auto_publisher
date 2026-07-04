"""模板文章生成服务。"""

import traceback

from ai_processor.content_writer import write_with_template
from ai_processor.image_generator import generate_cover_for_article
from ai_processor.processor import format_original_article
from database import get_db, init_default_templates, is_mysql
from domain.article_status import STATUS_DRAFT, split_legacy_status
from services.wechat_lead_card_adapter import append_lead_qr_at_end
from services.title_guard import TitleGuard


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
            db.commit()
            return {"ok": True, "article_id": article_id}
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
    def use_template(tmpl_id: int, topic: str) -> dict:
        """根据模板生成文章并写入数据库。"""
        if not topic:
            return {"ok": False, "msg": "请输入话题关键词"}

        conn = get_db()
        try:
            tmpl = TemplateService._select_template_by_id(conn, tmpl_id)
        finally:
            conn.close()

        if not tmpl:
            return {"ok": False, "msg": "模板不存在"}

        if not tmpl["is_active"]:
            return {"ok": False, "msg": "该模板已禁用，请启用后再使用"}

        article = write_with_template(topic=topic, template=dict(tmpl))
        if not article:
            return {"ok": False, "msg": "文章生成失败，请检查AI配置或网络"}

        try:
            article = format_original_article(article)
        except Exception:
            traceback.print_exc()

        # 生成封面失败时不阻塞主流程，只把状态写回数据库。
        cover_payload = generate_cover_for_article(
            article,
            style=dict(tmpl).get("category_label", "") or dict(tmpl).get("category", ""),
        )
        article.update(cover_payload)

        db = get_db()
        try:
            title = article.get("title", "").strip()
            existing = TemplateService._select_article_id_by_title(db, title)
            if existing:
                return {"ok": True, "msg": "该话题文章已存在，请前往文章列表查看"}

            review_status, publish_status = split_legacy_status(STATUS_DRAFT)
            TemplateService._insert_generated_article(
                db,
                article,
                topic,
                review_status,
                publish_status,
            )
            db.commit()
            return {"ok": True, "msg": "已生成 1 篇草稿，请前往文章列表查看"}
        finally:
            db.close()
