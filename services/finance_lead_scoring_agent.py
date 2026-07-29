"""Phase 4 lead scoring and customer profiling for finance consultations."""
from __future__ import annotations

import re
from typing import Any


class FinanceLeadScoringAgent:
    """Score financing leads with an explicit 30/25/20/15/10 model."""

    LEVEL_THRESHOLDS = (
        (90, "S"),
        (80, "A"),
        (65, "B"),
        (50, "C"),
        (0, "D"),
    )

    PROFILE_RULES = (
        ("现金流困难型", ("现金流", "周转", "垫资", "备货", "资金紧张")),
        ("额度不足型", ("额度低", "额度不足", "授信不足", "提额", "只批")),
        ("征信优化型", ("征信", "查询", "逾期")),
        ("贷款被拒型", ("拒贷", "被拒", "审批失败", "贷款失败")),
        ("融资规划型", ("融资规划", "扩大经营", "扩大生产", "设备采购", "债务优化", "融资成本")),
    )

    @classmethod
    def score(cls, customer: dict[str, Any] | None) -> dict[str, Any]:
        data = customer or {}
        need_score = cls._financing_need_score(data)
        quality_score = cls._enterprise_quality_score(data)
        document_score = cls._document_score(data)
        urgency_score = cls._urgency_score(data)
        credit_score = cls._credit_score(data)
        total = need_score + quality_score + document_score + urgency_score + credit_score
        level = cls._level(total)
        reasons = [
            f"融资需求明确度：{need_score}/30",
            f"企业质量：{quality_score}/25",
            f"资料完整度：{document_score}/20",
            f"时间紧迫度：{urgency_score}/15",
            f"信用情况：{credit_score}/10",
        ]
        return {
            "score": total,
            "level": level,
            "reason": reasons,
            "follow_action": cls._follow_action(level),
            "profile_tags": cls.profile_tags(data),
            "score_detail": {
                "financing_need": need_score,
                "enterprise_quality": quality_score,
                "data_completeness": document_score,
                "urgency": urgency_score,
                "credit": credit_score,
            },
        }

    @classmethod
    def profile_tags(cls, customer: dict[str, Any] | None) -> list[str]:
        data = customer or {}
        searchable = " ".join(
            str(data.get(key) or "")
            for key in (
                "pain_point",
                "financing_need",
                "financing_purpose",
                "scenario",
                "description",
                "notes",
            )
        )
        tags = [
            label
            for label, keywords in cls.PROFILE_RULES
            if any(keyword in searchable for keyword in keywords)
        ]
        return tags or ["融资规划型"]

    @classmethod
    def _financing_need_score(cls, data: dict[str, Any]) -> int:
        need = str(data.get("financing_need") or data.get("pain_point") or "").strip()
        purpose = str(data.get("financing_purpose") or data.get("scenario") or "").strip()
        amount = cls._number(
            data.get("financing_amount")
            or data.get("loan_amount")
            or data.get("required_amount")
        )
        explicit = cls._truthy(data.get("need_explicit"))
        if (need or explicit) and purpose and amount > 0:
            return 30
        if (need or explicit) and (purpose or amount > 0):
            return 24
        if need or purpose or amount > 0:
            return 15
        return 0

    @classmethod
    def _enterprise_quality_score(cls, data: dict[str, Any]) -> int:
        years = cls._number(
            data.get("business_years")
            or data.get("operating_years")
            or data.get("established_years")
        )
        revenue = cls._money(
            data.get("annual_revenue")
            or data.get("annual_turnover")
            or data.get("revenue")
        )
        quality = 0
        if years >= 3:
            quality += 10
        elif years >= 1:
            quality += 6
        elif years > 0:
            quality += 3
        if revenue >= 5_000_000:
            quality += 10
        elif revenue >= 1_000_000:
            quality += 7
        elif revenue > 0:
            quality += 3
        status = str(
            data.get("operating_status")
            or data.get("profit_status")
            or data.get("business_status")
            or ""
        )
        if cls._truthy(data.get("stable_operation")) or any(
            word in status for word in ("稳定", "盈利", "正常", "增长")
        ):
            quality += 5
        return min(25, quality)

    @classmethod
    def _document_score(cls, data: dict[str, Any]) -> int:
        if cls._truthy(data.get("documents_complete")):
            return 20
        documents = data.get("documents") or []
        if isinstance(documents, str):
            documents = [part.strip() for part in re.split(r"[,，、\s]+", documents) if part.strip()]
        supplied = {str(item).lower() for item in documents}
        aliases = (
            ("business_license", "营业执照"),
            ("bank_statements", "流水"),
            ("financial_statements", "财务报表"),
            ("tax_records", "纳税"),
            ("credit_report", "征信报告"),
        )
        score = 0
        for field, label in aliases:
            if cls._truthy(data.get(field)) or field in supplied or label in supplied:
                score += 4
        return min(20, score)

    @classmethod
    def _urgency_score(cls, data: dict[str, Any]) -> int:
        days = cls._number(data.get("funding_days") or data.get("required_in_days"))
        urgency = str(data.get("urgency") or data.get("timeline") or "").lower()
        if (0 < days <= 7) or any(word in urgency for word in ("非常紧急", "立即", "一周", "urgent")):
            return 15
        if (0 < days <= 30) or any(word in urgency for word in ("较急", "本月", "soon")):
            return 10
        if days > 0 or urgency:
            return 5
        return 0

    @classmethod
    def _credit_score(cls, data: dict[str, Any]) -> int:
        credit = str(
            data.get("credit_status")
            or data.get("credit")
            or data.get("overdue_status")
            or ""
        ).lower()
        if cls._truthy(data.get("good_credit")) or any(
            word in credit for word in ("良好", "无逾期", "正常", "good")
        ):
            return 10
        if any(word in credit for word in ("轻微", "少量查询", "偶尔", "minor")):
            return 5
        if credit:
            return 0
        return 5

    @classmethod
    def _level(cls, score: int) -> str:
        return next(level for threshold, level in cls.LEVEL_THRESHOLDS if score >= threshold)

    @staticmethod
    def _follow_action(level: str) -> str:
        return {
            "S": "立即分配融资顾问，1小时内完成需求确认并预约诊断。",
            "A": "2小时内联系，补齐授信资料并安排融资方案沟通。",
            "B": "24小时内完成初步诊断，确认产品匹配和资料缺口。",
            "C": "进入培育池，发送资料清单并在条件改善后复评。",
            "D": "进入长期培育，先提供基础融资规划建议。",
        }[level]

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "是", "有", "完整"}

    @staticmethod
    def _number(value: Any) -> float:
        try:
            if isinstance(value, str):
                matched = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
                return float(matched.group()) if matched else 0
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _money(cls, value: Any) -> float:
        number = cls._number(value)
        text = str(value or "")
        if "亿" in text:
            return number * 100_000_000
        if "万" in text:
            return number * 10_000
        return number
