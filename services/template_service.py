"""模板文章生成服务。"""

import traceback

from ai_processor.content_writer import optimize_wechat_title, write_with_template
from ai_processor.processor import format_original_article
from database import get_db, is_mysql
from domain.article_status import STATUS_DRAFT, split_legacy_status


class TemplateService:
    """封装模板生成文章的业务逻辑。"""

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
        """将模板生成文章写入数据库，显式区分两端占位符。"""
        params = (
            article.get("title", topic),
            article.get("content", ""),
            article.get("summary", ""),
            article.get("cover_url", ""),
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
                (title, content, summary, cover_url, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                params,
            )
            return

        db.execute(
            """
            INSERT INTO articles
            (title, content, summary, cover_url, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            params,
        )

    @staticmethod
    def use_template(tmpl_id: int, topic: str) -> dict:
        """根据模板生成文章并写入数据库。"""
        # 统一处理话题参数校验，保持原有返回文案不变。
        if not topic:
            return {"ok": False, "msg": "请输入话题关键词"}

        conn = get_db()
        try:
            # 先查询模板，模板不存在时直接返回。
            tmpl = TemplateService._select_template_by_id(conn, tmpl_id)
        finally:
            conn.close()

        if not tmpl:
            return {"ok": False, "msg": "模板不存在"}

        # 禁用模板不允许继续生成，避免绕过页面按钮直接调用接口。
        if not tmpl["is_active"]:
            return {"ok": False, "msg": "该模板已禁用，请启用后再使用"}

        # 将 sqlite3.Row 转为普通字典，兼容下游 .get 调用。
        article = write_with_template(topic=topic, template=dict(tmpl))
        if not article:
            return {"ok": False, "msg": "文章生成失败，请检查AI配置或网络"}

        # 先优化标题，再生成预览 HTML，确保文章列表标题和详情页标题横幅一致。
        article["title"] = optimize_wechat_title(article.get("title", topic))

        # 原创文章格式化失败时仅打印异常，保持原先不中断的行为。
        try:
            article = format_original_article(article)
        except Exception:
            traceback.print_exc()

        db = get_db()
        try:
            # 继续沿用标题去重逻辑，避免重复写入草稿。
            title = article.get("title", "").strip()
            existing = TemplateService._select_article_id_by_title(db, title)
            if existing:
                return {"ok": True, "msg": "该话题文章已存在，请前往文章列表查看"}

            # 按原字段写入文章，确保状态和原创标记不变。
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
