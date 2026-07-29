"""Phase 6 follow-up planning for enterprise-finance customers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class FinanceFollowupAgent:
    """Generate a stage-aware follow-up task for S/A/B/C/D customers."""

    LEVEL_PLANS = {
        "S": {
            "default_stage": "方案确认",
            "next_action": "立即确认融资方案并预约银行申请前资料复核",
            "delay_hours": 1,
            "focus": ["确认金额、用途和期限", "确认主方案与备选方案", "锁定资料提交时间"],
        },
        "A": {
            "default_stage": "资料收集",
            "next_action": "补齐关键资料并完成产品预匹配",
            "delay_hours": 2,
            "focus": ["经营和现金流优势", "资料缺口", "申请顺序和时间安排"],
        },
        "B": {
            "default_stage": "初步沟通",
            "next_action": "完成融资条件复核并制定优化清单",
            "delay_hours": 24,
            "focus": ["现金流覆盖", "负债压力", "征信查询和申请节奏"],
        },
        "C": {
            "default_stage": "线索进入",
            "next_action": "进入培育并约定条件改善后的复评时间",
            "delay_hours": 72,
            "focus": ["当前不宜申请的原因", "30至90天优化动作", "资料规范化"],
        },
        "D": {
            "default_stage": "线索进入",
            "next_action": "发送基础资料清单并进入长期培育",
            "delay_hours": 168,
            "focus": ["经营与信用基础", "禁止虚假包装", "重新诊断所需条件"],
        },
    }

    @classmethod
    def generate(
        cls,
        diagnosis: dict[str, Any] | None,
        customer: dict[str, Any] | None = None,
        project: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        safe_diagnosis = diagnosis or {}
        level = str(safe_diagnosis.get("level") or (customer or {}).get("level") or "D").upper()
        if level not in cls.LEVEL_PLANS:
            level = "D"
        plan = cls.LEVEL_PLANS[level]
        base_time = now or datetime.now()
        due_at = base_time + timedelta(hours=plan["delay_hours"])
        risks = list(safe_diagnosis.get("risks") or [])
        return {
            "level": level,
            "customer_stage": str(
                (project or {}).get("current_stage")
                or (customer or {}).get("finance_stage")
                or plan["default_stage"]
            ),
            "next_action": plan["next_action"],
            "followup_time": cls._time_label(plan["delay_hours"]),
            "followup_due_at": due_at.isoformat(timespec="minutes"),
            "communication_focus": list(plan["focus"]) + risks[:1],
        }

    @staticmethod
    def _time_label(hours: int) -> str:
        if hours < 24:
            return f"{hours}小时内"
        if hours == 24:
            return "24小时内"
        return f"{hours // 24}天内"
