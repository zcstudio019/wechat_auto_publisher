"""文章审核服务。"""

from database import get_db, is_mysql
from domain.article_status import REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED


class ReviewService:
    """封装文章人工审核相关业务逻辑。"""

    @staticmethod
    def _select_article_by_id(conn, article_id: int):
        if is_mysql():
            return conn.execute("SELECT * FROM articles WHERE id=%s", (article_id,)).fetchone()
        return conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()

    @staticmethod
    def _update_review_status(conn, article_id: int, review_status: str):
        """审核动作只写 review_status，不创建任务、不改变发布状态。"""
        if is_mysql():
            conn.execute(
                """
                UPDATE articles
                SET review_status=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (review_status, article_id),
            )
            return
        conn.execute(
            """
            UPDATE articles
            SET review_status=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (review_status, article_id),
        )

    @staticmethod
    def approve_article(article_id: int) -> tuple[dict, int]:
        """人工审核通过；文章进入已审核池，等待人工推送微信草稿箱。"""
        conn = get_db()
        try:
            article = ReviewService._select_article_by_id(conn, article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404

            ReviewService._update_review_status(conn, article_id, REVIEW_STATUS_APPROVED)
            conn.commit()
            return {
                "ok": True,
                "msg": "审核已通过，文章已进入已审核文章池",
            }, 200
        finally:
            conn.close()

    @staticmethod
    def reject_article(article_id: int) -> tuple[dict, int]:
        """人工审核拒绝；只更新审核结论。"""
        conn = get_db()
        try:
            article = ReviewService._select_article_by_id(conn, article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404
            ReviewService._update_review_status(conn, article_id, REVIEW_STATUS_REJECTED)
            conn.commit()
            return {"ok": True, "msg": "已拒绝"}, 200
        finally:
            conn.close()