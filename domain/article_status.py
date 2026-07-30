"""文章状态常量、拆分状态常量与兼容映射规则。"""

# 旧版兼容状态与新人工发布状态机。
STATUS_DRAFT = "draft"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_APPROVED = "approved"
STATUS_DRAFT_SENT = "draft_sent"
STATUS_WECHAT_DRAFT = "wechat_draft"
STATUS_WAITING_PUBLISH = "waiting_publish"
STATUS_PUBLISHED = "published"
STATUS_REJECTED = "rejected"
STATUS_ERROR = "error"
STATUS_FAILED = "failed"

# 审核状态。
REVIEW_STATUS_PENDING_REVIEW = "pending_review"
REVIEW_STATUS_DRAFT = REVIEW_STATUS_PENDING_REVIEW
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"

# 发布状态。
PUBLISH_STATUS_NOT_READY = "not_ready"
PUBLISH_STATUS_WECHAT_DRAFT = "wechat_draft"
PUBLISH_STATUS_WAITING_PUBLISH = "waiting_publish"
PUBLISH_STATUS_PUBLISHED = "published"
PUBLISH_STATUS_FAILED = "failed"
# 兼容旧调用名称；新流程不会再写 draft_sent。
PUBLISH_STATUS_DRAFT_SENT = PUBLISH_STATUS_WECHAT_DRAFT

ALL_ARTICLE_STATUSES = {
    STATUS_DRAFT,
    STATUS_PENDING_REVIEW,
    STATUS_APPROVED,
    STATUS_DRAFT_SENT,
    STATUS_WECHAT_DRAFT,
    STATUS_WAITING_PUBLISH,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_ERROR,
    STATUS_FAILED,
}


def split_legacy_status(status: str) -> tuple[str, str]:
    """根据兼容 status 计算 review_status 与 publish_status。"""
    mapping = {
        STATUS_DRAFT: (REVIEW_STATUS_PENDING_REVIEW, PUBLISH_STATUS_NOT_READY),
        STATUS_PENDING_REVIEW: (REVIEW_STATUS_PENDING_REVIEW, PUBLISH_STATUS_NOT_READY),
        STATUS_APPROVED: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_NOT_READY),
        STATUS_DRAFT_SENT: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_WECHAT_DRAFT),
        STATUS_WECHAT_DRAFT: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_WECHAT_DRAFT),
        STATUS_WAITING_PUBLISH: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_WAITING_PUBLISH),
        STATUS_PUBLISHED: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_PUBLISHED),
        STATUS_REJECTED: (REVIEW_STATUS_REJECTED, PUBLISH_STATUS_NOT_READY),
        STATUS_ERROR: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_FAILED),
        STATUS_FAILED: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_FAILED),
    }
    return mapping.get(status, (REVIEW_STATUS_PENDING_REVIEW, PUBLISH_STATUS_NOT_READY))


def is_approvable(status: str) -> bool:
    """判断兼容 status 是否可以进入审核通过流程。"""
    return status in {STATUS_DRAFT, STATUS_PENDING_REVIEW}


def is_publishable(status: str) -> bool:
    """判断兼容 status 是否可以人工推送到微信草稿箱。"""
    return status == STATUS_APPROVED


def is_rejectable(status: str) -> bool:
    """判断兼容 status 是否可以被拒绝。"""
    return status in {
        STATUS_DRAFT,
        STATUS_PENDING_REVIEW,
        STATUS_APPROVED,
        STATUS_DRAFT_SENT,
        STATUS_WECHAT_DRAFT,
        STATUS_WAITING_PUBLISH,
        STATUS_ERROR,
        STATUS_FAILED,
    }


def is_draft_like(status: str) -> bool:
    """判断状态是否属于未真实发表阶段。"""
    return status in {
        STATUS_DRAFT,
        STATUS_PENDING_REVIEW,
        STATUS_DRAFT_SENT,
        STATUS_WECHAT_DRAFT,
    }
