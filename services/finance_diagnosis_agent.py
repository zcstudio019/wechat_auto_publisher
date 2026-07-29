"""Phase 5 enterprise financing diagnosis agent."""
from __future__ import annotations

import re
from typing import Any


class FinanceDiagnosisAgent:
    """Produce a deterministic financing diagnosis without relying on an LLM."""

    LEVEL_THRESHOLDS = ((90, "S"), (80, "A"), (65, "B"), (50, "C"), (0, "D"))

    @classmethod
    def diagnose(cls, enterprise: dict[str, Any] | None) -> dict[str, Any]:
        data = enterprise or {}
        operation = cls._operation_score(data)
        cash_flow = cls._cash_flow_score(data)
        debt = cls._debt_score(data)
        credit = cls._credit_score(data)
        financing_need = cls._need_score(data)
        score = operation + cash_flow + debt + credit + financing_need
        level = cls._level(score)

        advantages = cls._advantages(data, operation, cash_flow, debt, credit, financing_need)
        risks = cls._risks(data, operation, cash_flow, debt, credit, financing_need)
        problems = cls._problems(data, operation, cash_flow, debt, credit, financing_need)
        recommendations = cls._recommendations(data, problems)
        return {
            "score": score,
            "level": level,
            "financing_capacity": cls._capacity(data, score),
            "advantages": advantages,
            "risks": risks,
            "problems": problems,
            "recommendations": recommendations,
            "required_documents": cls._required_documents(data),
            "score_detail": {
                "enterprise_operation": operation,
                "cash_flow": cash_flow,
                "debt": debt,
                "credit": credit,
                "financing_need": financing_need,
            },
        }

    @classmethod
    def _operation_score(cls, data: dict[str, Any]) -> int:
        years = cls._number(data.get("business_years") or data.get("operating_years"))
        revenue = cls._money(
            data.get("annual_revenue") or data.get("annual_turnover") or data.get("revenue")
        )
        status = cls._text(data, "operating_status", "business_status", "profit_status")
        score = 0
        if years >= 3:
            score += 12
        elif years >= 1:
            score += 8
        elif years > 0:
            score += 4
        if revenue >= 5_000_000:
            score += 12
        elif revenue >= 1_000_000:
            score += 8
        elif revenue > 0:
            score += 4
        if cls._truthy(data.get("stable_operation")) or any(
            word in status for word in ("稳定", "盈利", "增长", "正常")
        ):
            score += 6
        return min(30, score)

    @classmethod
    def _cash_flow_score(cls, data: dict[str, Any]) -> int:
        annual_cash = cls._money(
            data.get("annual_cash_inflow")
            or data.get("annual_bank_flow")
            or data.get("annual_revenue")
        )
        monthly_repayment = cls._money(
            data.get("monthly_repayment") or data.get("monthly_debt_payment")
        )
        monthly_cash = annual_cash / 12 if annual_cash else 0
        status = cls._text(data, "cash_flow_status", "cash_flow", "payment_collection")
        if any(word in status for word in ("断裂", "严重紧张", "持续为负")):
            return 3
        if monthly_cash and monthly_repayment:
            coverage = monthly_cash / max(1, monthly_repayment)
            if coverage >= 3:
                return 25
            if coverage >= 2:
                return 20
            if coverage >= 1.2:
                return 14
            return 6
        if any(word in status for word in ("充足", "稳定", "良好", "正常")):
            return 22
        if any(word in status for word in ("紧张", "波动", "回款慢")):
            return 10
        if annual_cash > 0:
            return 15
        return 5

    @classmethod
    def _debt_score(cls, data: dict[str, Any]) -> int:
        debt_ratio = cls._ratio(data.get("debt_ratio") or data.get("liability_ratio"))
        total_debt = cls._money(data.get("total_debt") or data.get("liabilities"))
        annual_revenue = cls._money(data.get("annual_revenue") or data.get("annual_turnover"))
        status = cls._text(data, "debt_status", "liability_status")
        if debt_ratio <= 0 and total_debt and annual_revenue:
            debt_ratio = total_debt / max(1, annual_revenue)
        if any(word in status for word in ("很低", "无负债", "低负债")):
            return 20
        if debt_ratio:
            if debt_ratio <= 0.3:
                return 20
            if debt_ratio <= 0.5:
                return 16
            if debt_ratio <= 0.7:
                return 10
            return 3
        if any(word in status for word in ("高负债", "逾期", "集中到期")):
            return 3
        return 10

    @classmethod
    def _credit_score(cls, data: dict[str, Any]) -> int:
        status = cls._text(data, "credit_status", "credit", "overdue_status")
        if cls._truthy(data.get("good_credit")) or any(
            word in status for word in ("良好", "无逾期", "正常", "优秀")
        ):
            return 15
        if any(word in status for word in ("轻微", "偶尔", "查询偏多", "少量查询")):
            return 9
        if any(word in status for word in ("当前逾期", "严重", "失信", "呆账")):
            return 0
        if status:
            return 5
        return 7

    @classmethod
    def _need_score(cls, data: dict[str, Any]) -> int:
        need = cls._text(data, "financing_need", "financing_purpose", "loan_purpose", "description")
        amount = cls._money(
            data.get("financing_amount")
            or data.get("loan_amount")
            or data.get("required_amount")
        )
        timeline = cls._text(data, "timeline", "urgency")
        if need and amount and timeline:
            return 10
        if need and amount:
            return 8
        if need or amount:
            return 5
        return 0

    @classmethod
    def _advantages(
        cls, data: dict[str, Any], operation: int, cash: int, debt: int, credit: int, need: int
    ) -> list[str]:
        items = []
        if operation >= 24:
            items.append("企业经营年限、营收和稳定性具备较好基础。")
        if cash >= 20:
            items.append("经营现金流对现有还款支出具有较好覆盖能力。")
        if debt >= 16:
            items.append("当前负债结构相对可控，仍有一定新增融资空间。")
        if credit >= 12:
            items.append("企业或法定代表人信用记录整体良好。")
        if need >= 8:
            items.append("融资金额和用途比较明确，便于匹配产品。")
        return items or ["已具备开展基础融资诊断所需的企业信息。"]

    @classmethod
    def _risks(
        cls, data: dict[str, Any], operation: int, cash: int, debt: int, credit: int, need: int
    ) -> list[str]:
        items = []
        if operation < 18:
            items.append("经营年限、营收或持续经营证据偏弱。")
        if cash < 14:
            items.append("现金流覆盖能力不足或回款稳定性需要进一步核验。")
        if debt < 10:
            items.append("负债率偏高或短期偿债压力较大。")
        if credit < 9:
            items.append("征信记录可能影响准入、额度或审批时效。")
        if need < 8:
            items.append("融资金额、用途或时间计划不够明确。")
        return items or ["当前未发现突出硬伤，仍需以银行正式审核为准。"]

    @classmethod
    def _problems(
        cls, data: dict[str, Any], operation: int, cash: int, debt: int, credit: int, need: int
    ) -> list[str]:
        dimensions = (
            ("企业经营资料不完整，银行难以确认持续经营能力。", operation, 18),
            ("回款、流水与月度还款之间尚未形成清晰闭环。", cash, 14),
            ("现有负债可能压缩新增授信空间。", debt, 10),
            ("征信情况需要在申请前进一步核验。", credit, 9),
            ("融资需求尚未形成明确的金额、用途和期限方案。", need, 8),
        )
        return [message for message, value, threshold in dimensions if value < threshold] or [
            "核心条件基本完整，主要问题转为产品口径与申请顺序匹配。"
        ]

    @staticmethod
    def _recommendations(data: dict[str, Any], problems: list[str]) -> list[str]:
        recommendations = [
            "先核对近12个月对公流水、开票、纳税和主要合同的一致性。",
            "测算新增融资后的月度还款压力，避免额度超过现金流承受能力。",
            "申请前集中核验企业与法定代表人征信，避免短期重复查询。",
            "根据融资用途、期限和担保条件筛选产品，再确定申请顺序。",
        ]
        if any("负债" in item for item in problems):
            recommendations.insert(1, "梳理短期到期负债和担保责任，优先处理高成本或集中到期债务。")
        return recommendations

    @classmethod
    def _required_documents(cls, data: dict[str, Any]) -> list[str]:
        required = [
            "营业执照及公司章程",
            "法定代表人和主要股东身份证明",
            "近12个月对公及主要经营流水",
            "近两年财务报表和近期科目余额表",
            "纳税、开票及主要经营合同",
            "企业和法定代表人征信报告",
            "现有借款、担保和抵押物清单",
            "融资用途说明及还款来源证明",
        ]
        supplied = " ".join(str(item) for item in (data.get("documents") or []))
        return [item for item in required if item not in supplied]

    @classmethod
    def _capacity(cls, data: dict[str, Any], score: int) -> str:
        revenue = cls._money(data.get("annual_revenue") or data.get("annual_turnover"))
        label = "较强" if score >= 85 else "中等" if score >= 65 else "偏弱" if score >= 50 else "较弱"
        if revenue:
            low = int(revenue * (0.08 if score < 65 else 0.12))
            high = int(revenue * (0.18 if score < 65 else 0.3))
            return f"{label}；基于现有资料的初步融资空间约{cls._format_money(low)}至{cls._format_money(high)}，以银行审核为准。"
        return f"{label}；资料不足，暂不估算具体额度，以银行审核为准。"

    @classmethod
    def _level(cls, score: int) -> str:
        return next(level for threshold, level in cls.LEVEL_THRESHOLDS if score >= threshold)

    @staticmethod
    def _format_money(value: float) -> str:
        return f"{round(value / 10_000)}万元" if value >= 10_000 else f"{round(value)}元"

    @staticmethod
    def _text(data: dict[str, Any], *keys: str) -> str:
        return " ".join(str(data.get(key) or "") for key in keys).strip()

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "是", "有", "良好"}

    @staticmethod
    def _number(value: Any) -> float:
        try:
            match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
            return float(match.group()) if match else 0
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

    @classmethod
    def _ratio(cls, value: Any) -> float:
        number = cls._number(value)
        return number / 100 if "%" in str(value or "") or number > 1 else number
