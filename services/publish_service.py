"""微信公众号人工草稿投递与发布状态确认服务。"""

from database import get_db, is_mysql
from domain.article_status import (
    PUBLISH_STATUS_FAILED,
    PUBLISH_STATUS_NOT_READY,
    PUBLISH_STATUS_PUBLISHED,
    PUBLISH_STATUS_WAITING_PUBLISH,
    PUBLISH_STATUS_WECHAT_DRAFT,
    REVIEW_STATUS_APPROVED,
)
from wechat_api.client import WechatPublishError
from wechat_api.publisher import publish_single_article


class PublishService:
    """人工推进文章的微信草稿与真实发表状态。"""

    @staticmethod
    def _select_article_by_id(conn, article_id: int):
        if is_mysql():
            return conn.execute("SELECT * FROM articles WHERE id=%s", (article_id,)).fetchone()
        return conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()

    @staticmethod
    def _is_review_approved(article) -> bool:
        return (
            str(article["review_status"] or "") == REVIEW_STATUS_APPROVED
            if "review_status" in article.keys()
            else str(article["status"] or "") == "approved"
        )

    @staticmethod
    def _publish_status(article) -> str:
        if "publish_status" not in article.keys():
            return PUBLISH_STATUS_NOT_READY
        return str(article["publish_status"] or PUBLISH_STATUS_NOT_READY)

    @staticmethod
    def _update_publish_status(
        conn,
        article_id: int,
        publish_status: str,
        *,
        media_id: str | None = None,
        mark_published: bool = False,
    ):
        assignments = ["publish_status=%s"] if is_mysql() else ["publish_status=?"]
        params = [publish_status]
        if media_id is not None:
            assignments.extend(
                ["wechat_media_id=%s", "draft_id=%s"]
                if is_mysql()
                else ["wechat_media_id=?", "draft_id=?"]
            )
            params.extend([media_id, media_id])
        if mark_published:
            assignments.append(
                "published_at=CURRENT_TIMESTAMP"
                if is_mysql()
                else "published_at=datetime('now','localtime')"
            )
        assignments.append(
            "updated_at=CURRENT_TIMESTAMP"
            if is_mysql()
            else "updated_at=datetime('now','localtime')"
        )
        placeholder = "%s" if is_mysql() else "?"
        params.append(article_id)
        conn.execute(
            f"UPDATE articles SET {', '.join(assignments)} WHERE id={placeholder}",
            tuple(params),
        )

    @staticmethod
    def _mark_push_failed(conn, article_id: int):
        PublishService._update_publish_status(conn, article_id, PUBLISH_STATUS_FAILED)
        conn.commit()

    @staticmethod
    def publish_approved() -> tuple[dict, int]:
        """人工批量推送已审核池文章到微信草稿箱，不创建发布任务。"""
        conn = get_db()
        try:
            placeholder = "%s" if is_mysql() else "?"
            rows = conn.execute(
                f"""
                SELECT id FROM articles
                WHERE review_status={placeholder}
                  AND (publish_status IS NULL OR publish_status IN ({placeholder}, {placeholder}))
                ORDER BY created_at DESC
                """,
                (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_NOT_READY, PUBLISH_STATUS_FAILED),
            ).fetchall()
        finally:
            conn.close()

        success_count = 0
        failed_count = 0
        for row in rows:
            result, _ = PublishService.push_single_article(row["id"])
            if result.get("ok"):
                success_count += 1
            else:
                failed_count += 1
        return {
            "ok": True,
            "msg": f"已人工推送 {success_count} 篇到微信草稿箱",
            "success_count": success_count,
            "failed_count": failed_count,
        }, 200

    @staticmethod
    def push_single_article(article_id: int) -> tuple[dict, int]:
        """人工推送单篇已审核文章到微信草稿箱；绝不调用发表接口。"""
        conn = get_db()
        try:
            article = PublishService._select_article_by_id(conn, article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404
            if not PublishService._is_review_approved(article):
                return {"ok": False, "msg": "只能推送人工审核通过的文章"}, 400

            current_status = PublishService._publish_status(article)
            if current_status not in {PUBLISH_STATUS_NOT_READY, PUBLISH_STATUS_FAILED}:
                return {"ok": False, "msg": "文章当前状态不允许重复推送微信草稿箱"}, 400

            try:
                media_id = publish_single_article(dict(article), auto_submit=False)
            except WechatPublishError as exc:
                PublishService._mark_push_failed(conn, article_id)
                return {"ok": False, "msg": str(exc), **exc.to_dict()}, 200
            except Exception as exc:
                PublishService._mark_push_failed(conn, article_id)
                return {"ok": False, "msg": f"推送异常: {exc}"}, 200

            if not media_id:
                PublishService._mark_push_failed(conn, article_id)
                return {"ok": False, "msg": "推送失败：微信未返回草稿 media_id"}, 200

            PublishService._update_publish_status(
                conn,
                article_id,
                PUBLISH_STATUS_WECHAT_DRAFT,
                media_id=media_id,
            )
            conn.commit()
            return {
                "ok": True,
                "msg": "已推送到微信公众号草稿箱，请在公众号后台人工检查",
                "wechat_media_id": media_id,
                "draft_id": media_id,
                "publish_status": PUBLISH_STATUS_WECHAT_DRAFT,
            }, 200
        finally:
            conn.close()

    @staticmethod
    def mark_waiting_publish(article_id: int) -> tuple[dict, int]:
        """人工确认微信草稿检查完成，进入等待公众号人工发表阶段。"""
        conn = get_db()
        try:
            article = PublishService._select_article_by_id(conn, article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404
            if PublishService._publish_status(article) != PUBLISH_STATUS_WECHAT_DRAFT:
                return {"ok": False, "msg": "只有微信草稿才能进入等待人工发表"}, 400
            PublishService._update_publish_status(conn, article_id, PUBLISH_STATUS_WAITING_PUBLISH)
            conn.commit()
            return {
                "ok": True,
                "msg": "草稿已检查，等待在微信公众号后台人工发表",
                "publish_status": PUBLISH_STATUS_WAITING_PUBLISH,
            }, 200
        finally:
            conn.close()

    @staticmethod
    def confirm_published(article_id: int) -> tuple[dict, int]:
        """人工确认公众号已经真实发表；此方法不调用任何微信发表接口。"""
        conn = get_db()
        try:
            article = PublishService._select_article_by_id(conn, article_id)
            if not article:
                return {"ok": False, "msg": "文章不存在"}, 404
            if PublishService._publish_status(article) != PUBLISH_STATUS_WAITING_PUBLISH:
                return {"ok": False, "msg": "只有等待人工发表的文章才能确认已发布"}, 400
            PublishService._update_publish_status(
                conn,
                article_id,
                PUBLISH_STATUS_PUBLISHED,
                mark_published=True,
            )
            conn.commit()
            return {
                "ok": True,
                "msg": "已确认公众号真实发表",
                "publish_status": PUBLISH_STATUS_PUBLISHED,
            }, 200
        finally:
            conn.close()