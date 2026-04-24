"""文章审核服务。"""

from config import REVIEW_APPROVE_EXECUTE_IMMEDIATELY
from database import get_db, is_mysql
from domain.article_status import (
    STATUS_APPROVED,
    STATUS_REJECTED,
    split_legacy_status,
)
from services.publish_task_service import PublishTaskService


class ReviewService:
    """封装文章审核相关的业务逻辑。"""

    @staticmethod
    def _select_article_by_id(conn, article_id: int):
        """按主键查询文章，显式兼容 SQLite / MySQL。"""
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
    def _update_article_review_status(conn, article_id: int, status: str, review_status: str, publish_status: str):
        """统一回写审核与发布状态，减少两端时间函数写法散落。"""
        if is_mysql():
            conn.execute(
                """
                UPDATE articles
                SET status=%s, review_status=%s, publish_status=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (status, review_status, publish_status, article_id),
            )
            return

        conn.execute(
            """
            UPDATE articles
            SET status=?, review_status=?, publish_status=?, updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (status, review_status, publish_status, article_id),
        )

    @staticmethod
    def approve_article(article_id: int) -> tuple[dict, int]:
        """审核通过文章，并保留原有自动推送草稿箱的行为。"""
        conn = get_db()
        try:
            # 先查询文章，保持原有不存在时返回 404 的行为。
            article = ReviewService._select_article_by_id(conn, article_id)

            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404

            # 先更新为已审核，保持与原逻辑一致。
            review_status, publish_status = split_legacy_status(STATUS_APPROVED)
            ReviewService._update_article_review_status(
                conn,
                article_id,
                STATUS_APPROVED,
                review_status,
                publish_status,
            )
            conn.commit()

            # 审核通过后仍然先创建发布任务，为完全异步化保留统一入口。
            task_id = PublishTaskService.create_task_for_article(article_id=article_id)

            # 默认保持立即同步执行，确保现有行为不变。
            if not REVIEW_APPROVE_EXECUTE_IMMEDIATELY:
                return {
                    "ok": True,
                    "msg": "已通过审核并加入发布队列",
                    "task_id": task_id,
                }, 200

            # 配置开启时继续同步执行任务，保持外部体验仍然是立即完成。
            task_result = PublishTaskService.execute_task(task_id)

            if task_result.get("ok") and task_result.get("draft_id"):
                return {
                    "ok": True,
                    "msg": "已通过审核并推送到微信草稿箱",
                    "draft_id": task_result["draft_id"],
                }, 200

            if task_result.get("is_exception"):
                # 保持原有行为：即使推送异常，审核结果仍然算成功。
                return {"ok": True, "msg": f"已通过审核，推送异常: {task_result.get('msg', '')}"}, 200

            # 保持原有行为：推送失败时审核仍算成功，仅提示手动处理。
            return {"ok": True, "msg": "已通过审核，但推送草稿箱失败，请手动推送"}, 200
        finally:
            conn.close()

    @staticmethod
    def reject_article(article_id: int) -> tuple[dict, int]:
        """审核拒绝文章。"""
        conn = get_db()
        try:
            # 保持原有行为：不额外校验文章是否存在，直接执行状态更新。
            review_status, publish_status = split_legacy_status(STATUS_REJECTED)
            ReviewService._update_article_review_status(
                conn,
                article_id,
                STATUS_REJECTED,
                review_status,
                publish_status,
            )
            conn.commit()
            return {"ok": True, "msg": "已拒绝"}, 200
        finally:
            conn.close()
