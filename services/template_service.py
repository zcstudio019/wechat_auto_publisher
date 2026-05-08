"""模板文章生成服务。"""

import traceback

from ai_processor.content_writer import optimize_wechat_title, write_with_template
from ai_processor.image_generator import generate_cover_for_article
from ai_processor.processor import format_original_article
from database import get_db, init_default_templates, is_mysql
from domain.article_status import STATUS_DRAFT, split_legacy_status


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
        params = (
            article.get("title", topic),
            article.get("content", ""),
            article.get("summary", ""),
            article.get("cover_url", ""),
            article.get("cover_image", ""),
            article.get("cover_status", "pending"),
            article.get("cover_prompt", ""),
            article.get("source_name", "沪上银原创"),
            article.get("source_url", ""),
            article.get("tags", f"{topic},原创"),
            STATUS_DRAFT,
            review_status,
            publish_status,
            1,
            article.get("html_content", ""),
        )

        if is_mysql():
            db.execute(
                """
                INSERT INTO articles
                (title, content, summary, cover_url, cover_image, cover_status, cover_prompt, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                params,
            )
            return

        db.execute(
            """
            INSERT INTO articles
            (title, content, summary, cover_url, cover_image, cover_status, cover_prompt, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            params,
        )

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

        # 先优化标题，再做正文格式化，确保封面提示词与详情页标题一致。
        article["title"] = optimize_wechat_title(article.get("title", topic))

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
