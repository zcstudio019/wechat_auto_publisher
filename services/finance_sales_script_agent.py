"""Phase 6 compliant sales-script generator."""
from __future__ import annotations

from typing import Any


class FinanceSalesScriptAgent:
    """Generate phone, WeChat, objection and closing scripts."""

    @classmethod
    def generate(
        cls,
        level: str,
        financing_need: str = "",
        risks: list[str] | None = None,
        customer_name: str = "",
    ) -> dict[str, str]:
        safe_level = str(level or "D").upper()
        if safe_level not in {"S", "A", "B", "C", "D"}:
            safe_level = "D"
        name = str(customer_name or "老板")
        need = str(financing_need or "企业融资")
        risk_text = "；".join(str(item) for item in (risks or [])[:2]) or "资料完整性和银行准入口径"
        urgency = {
            "S": "今天",
            "A": "本次沟通后",
            "B": "资料核验后",
            "C": "条件优化后",
            "D": "基础条件成熟后",
        }[safe_level]
        return {
            "level": safe_level,
            "first_call_script": (
                f"{name}您好，我看过您关于“{need}”的资料，目前初步等级为{safe_level}。"
                f"这次先核对经营、现金流、负债和用途，重点确认{risk_text}。"
                "具体额度、期限和审批结果以银行审核为准。"
            ),
            "wechat_followup_script": (
                f"{name}您好，刚才沟通的“{need}”我已整理。下一步建议{urgency}完成资料核验，"
                "我会根据真实经营条件提供主方案和备选方向，不会要求多头盲目申请。"
            ),
            "objection_handling_script": (
                "您关心额度、利率和是否能批很正常。现在直接承诺结果并不负责，"
                f"因为目前仍需确认{risk_text}。先把影响审批的条件查清，再比较方案，能减少试错和征信查询。"
            ),
            "closing_script": (
                f"如果您认可，我们下一步就围绕“{need}”确认资料清单、方案顺序和提交时间。"
                "方案确认后再进入银行申请，所有结果以银行正式审核为准。"
            ),
        }
