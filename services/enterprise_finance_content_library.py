"""Curated content assets for the enterprise-finance growth agent."""
from __future__ import annotations

from typing import Any


OWNER_PAIN_POINTS = (
    "现金流紧张",
    "银行拒贷",
    "额度不足",
    "征信问题",
    "负债过高",
    "续贷困难",
    "经营贷申请",
    "企业扩张资金不足",
    "融资成本过高",
    "贷款申请频繁失败",
)

FINANCING_SCENARIOS = (
    "申请经营贷",
    "企业周转",
    "扩大生产",
    "设备采购",
    "库存备货",
    "项目垫资",
    "股东资金退出",
    "债务优化",
    "融资规划",
)

CUSTOMER_PROFILES = (
    "初创企业老板",
    "经营3年以上老板",
    "年流水100万-500万老板",
    "年流水500万以上老板",
    "高负债老板",
    "现金流困难老板",
)

INDUSTRY_HOTSPOTS = (
    "银行经营贷审核更关注真实现金流",
    "企业授信额度与负债结构联动",
    "续贷前需要提前检查授信条件",
    "频繁申请贷款会增加征信查询",
    "企业扩张前需要规划中长期融资",
)

DEFAULT_CTA = {
    "title": "企业融资体检",
    "description": "提供企业成立时间、营业额、负债情况和融资需求，帮你判断融资空间、额度可能性和优化方向。",
    "button_text": "开始融资条件诊断",
}

CTA_RULES = (
    (
        ("现金流", "周转", "项目垫资", "库存备货"),
        {
            "title": "现金流健康检测",
            "description": "结合回款周期、经营支出、现有负债和资金缺口，判断现金流风险与融资节奏。",
            "button_text": "开始现金流检测",
        },
    ),
    (
        ("征信", "查询", "逾期"),
        {
            "title": "征信优化诊断",
            "description": "检查企业与法人的查询、负债、逾期和担保情况，判断影响审批的征信信号。",
            "button_text": "开始征信诊断",
        },
    ),
    (
        ("额度", "授信"),
        {
            "title": "融资额度评估",
            "description": "结合流水、利润、纳税、资产和负债，评估企业额度空间与提升方向。",
            "button_text": "开始额度评估",
        },
    ),
    (
        ("拒贷", "被拒", "申请频繁失败", "贷款失败"),
        {
            "title": "贷款失败原因分析",
            "description": "从现金流、征信、负债、经营稳定性和产品匹配度，定位贷款失败的主要原因。",
            "button_text": "分析失败原因",
        },
    ),
)


def match_finance_cta(topic: dict[str, Any] | None = None, title: str = "") -> dict[str, str]:
    """Return the CTA that best matches a topic's pain point and scenario."""
    safe_topic = topic or {}
    pain_point = str(safe_topic.get("pain_point") or "")
    for keywords, cta in CTA_RULES:
        if any(keyword in pain_point for keyword in keywords):
            return dict(cta)
    searchable = " ".join(
        str(value or "")
        for value in (
            safe_topic.get("pain_point"),
            safe_topic.get("scenario"),
            safe_topic.get("conversion_goal"),
            safe_topic.get("suggested_title"),
            safe_topic.get("title"),
            title,
        )
    )
    for keywords, cta in CTA_RULES:
        if any(keyword in searchable for keyword in keywords):
            return dict(cta)
    return dict(DEFAULT_CTA)
