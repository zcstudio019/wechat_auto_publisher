"""文章状态常量、拆分状态常量与兼容映射规则。"""

# 统一定义旧版兼容状态。
STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
STATUS_DRAFT_SENT = "draft_sent"
STATUS_PUBLISHED = "published"
STATUS_REJECTED = "rejected"
STATUS_ERROR = "error"

# 统一定义审核状态。
REVIEW_STATUS_DRAFT = "draft"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"

# 统一定义发布状态。
PUBLISH_STATUS_NOT_READY = "not_ready"
PUBLISH_STATUS_DRAFT_SENT = "draft_sent"
PUBLISH_STATUS_PUBLISHED = "published"
PUBLISH_STATUS_FAILED = "failed"

# 统一收口全部旧版文章状态。
ALL_ARTICLE_STATUSES = {
    STATUS_DRAFT,
    STATUS_APPROVED,
    STATUS_DRAFT_SENT,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_ERROR,
}


def split_legacy_status(status: str) -> tuple[str, str]:
    """根据旧版 status 计算 review_status 与 publish_status。"""
    # 统一维护旧状态到新字段的兼容映射规则。
    mapping = {
        STATUS_DRAFT: (REVIEW_STATUS_DRAFT, PUBLISH_STATUS_NOT_READY),
        STATUS_APPROVED: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_NOT_READY),
        STATUS_DRAFT_SENT: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_DRAFT_SENT),
        STATUS_PUBLISHED: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_PUBLISHED),
        STATUS_REJECTED: (REVIEW_STATUS_REJECTED, PUBLISH_STATUS_NOT_READY),
        STATUS_ERROR: (REVIEW_STATUS_APPROVED, PUBLISH_STATUS_FAILED),
    }
    # 未知状态时回退为草稿态，避免破坏现有流程。
    return mapping.get(status, (REVIEW_STATUS_DRAFT, PUBLISH_STATUS_NOT_READY))


def is_approvable(status: str) -> bool:
    """判断状态是否可以进入审核通过流程。"""
    # 现阶段保持草稿态可审核。
    return status == STATUS_DRAFT


def is_publishable(status: str) -> bool:
    """判断状态是否可以推送到微信草稿箱。"""
    # 现阶段保持已审核文章可推送。
    return status == STATUS_APPROVED


def is_rejectable(status: str) -> bool:
    """判断状态是否可以被拒绝。"""
    # 现阶段只提供轻量规则，不强制驱动业务分支。
    return status in {
        STATUS_DRAFT,
        STATUS_APPROVED,
        STATUS_DRAFT_SENT,
        STATUS_ERROR,
    }


def is_draft_like(status: str) -> bool:
    """判断状态是否属于草稿阶段。"""
    # 普通草稿和微信草稿箱中的草稿都视为草稿态。
    return status in {
        STATUS_DRAFT,
        STATUS_DRAFT_SENT,
    }
