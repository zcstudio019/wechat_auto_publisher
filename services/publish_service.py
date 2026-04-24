"""文章发布服务。"""

from database import get_db, is_mysql
from domain.article_status import STATUS_APPROVED, STATUS_DRAFT_SENT, is_publishable, split_legacy_status
from services.publish_task_service import PublishTaskService
from wechat_api.publisher import publish_single_article


class PublishService:
    """封装文章发布相关的业务逻辑。"""

    @staticmethod
    def _select_article_by_id(conn, article_id: int):
        """按主键读取文章，显式区分两端占位符。"""
        if is_mysql():
            return conn.execute(
                "SELECT * FROM articles WHERE id=%s",
                (article_id,),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM articles WHERE id=?",
            (article_id,),
        ).fetchone()

    @staticmethod
    def _update_article_draft_status(conn, article_id: int, media_id: str, review_status: str, publish_status: str):
        """回写草稿箱状态，显式区分两端时间函数。"""
        if is_mysql():
            conn.execute(
                """
                UPDATE articles
                SET status=%s, review_status=%s, publish_status=%s, draft_id=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (STATUS_DRAFT_SENT, review_status, publish_status, media_id, article_id),
            )
            return

        conn.execute(
            """
            UPDATE articles
            SET status=?, review_status=?, publish_status=?, draft_id=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (STATUS_DRAFT_SENT, review_status, publish_status, media_id, article_id),
        )

    @staticmethod
    def publish_approved() -> tuple[dict, int]:
        """批量推送已审核文章到微信草稿箱。"""
        conn = get_db()
        try:
            # 批量发布入口统一改走任务模型，但仍保持同步执行体验。
            if is_mysql():
                rows = conn.execute(
                    "SELECT id FROM articles WHERE status=%s ORDER BY created_at DESC",
                    (STATUS_APPROVED,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM articles WHERE status=? ORDER BY created_at DESC",
                    (STATUS_APPROVED,),
                ).fetchall()
        finally:
            conn.close()

        count = 0
        for row in rows:
            # 为每篇已审核文章创建发布任务，内部会自动避免重复创建有效任务。
            task_id = PublishTaskService.create_task_for_article(article_id=row["id"])

            # 当前阶段继续同步执行任务，保持运营侧原有即时发布体验。
            result = PublishTaskService.execute_task(task_id)
            if result.get("ok") and result.get("draft_id"):
                count += 1

        return {"ok": True, "msg": f"成功推送 {count} 篇到微信草稿箱"}, 200

    @staticmethod
    def push_single_article(article_id: int) -> tuple[dict, int]:
        """推送单篇已审核文章到微信草稿箱。"""
        conn = get_db()
        try:
            # 先查询文章，保持原有不存在时返回 404 的行为。
            article = PublishService._select_article_by_id(conn, article_id)

            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404

            # 保持原有状态校验：只能推送已审核的文章。
            if not is_publishable(article["status"]):
                return {"ok": False, "msg": "只能推送已审核的文章"}, 400

            # 调用原有单篇发布能力，保持推送逻辑不变。
            media_id = publish_single_article(dict(article))
            if media_id:
                review_status, publish_status = split_legacy_status(STATUS_DRAFT_SENT)
                PublishService._update_article_draft_status(
                    conn,
                    article_id,
                    media_id,
                    review_status,
                    publish_status,
                )
                conn.commit()
                return {"ok": True, "msg": "已推送到微信草稿箱", "draft_id": media_id}, 200

            return {"ok": False, "msg": "推送失败，请检查微信API配置"}, 200
        finally:
            conn.close()
