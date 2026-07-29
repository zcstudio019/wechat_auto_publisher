"""Phase 5 sales-assistance suggestions for financing advisors."""
from __future__ import annotations

from typing import Any


class FinanceSalesAssistantAgent:
    """Generate compliant follow-up guidance by diagnosis level."""

    PLAYBOOKS = {
        "S": {
            "follow_actions": ["立即分配资深融资顾问", "1小时内电话确认需求", "当天预约融资方案沟通"],
            "communication_focus": ["确认融资金额、用途和时间", "突出多产品比较和申请顺序", "快速核验关键资料"],
            "risk_alerts": ["避免承诺固定额度、利率或放款时间", "确认资金用途真实合规"],
            "next_tasks": ["收集完整资料", "完成产品预匹配", "形成一页融资方案"],
        },
        "A": {
            "follow_actions": ["2小时内联系客户", "安排融资条件诊断", "明确资料缺口"],
            "communication_focus": ["经营和现金流优势", "影响额度的关键短板", "可执行的资料准备计划"],
            "risk_alerts": ["不要在资料未核验前给出确定审批结论"],
            "next_tasks": ["补齐流水和征信", "筛选两至三个方向", "预约二次沟通"],
        },
        "B": {
            "follow_actions": ["24小时内完成首次沟通", "先做问题诊断再推荐产品"],
            "communication_focus": ["现金流、负债和征信短板", "申请前优化顺序"],
            "risk_alerts": ["避免客户短期内频繁申请", "说明当前方案存在不确定性"],
            "next_tasks": ["建立资料清单", "测算还款压力", "条件改善后复评"],
        },
        "C": {
            "follow_actions": ["进入重点培育池", "发送融资基础资料清单"],
            "communication_focus": ["解释暂不申请的原因", "给出30至90天优化路径"],
            "risk_alerts": ["不建议立即多头申请", "警惕高成本过桥和违规包装"],
            "next_tasks": ["补经营证明", "降低短期负债", "30天后重新评分"],
        },
        "D": {
            "follow_actions": ["进入长期培育池", "先提供基础融资教育"],
            "communication_focus": ["明确当前资料和条件缺口", "建立企业规范经营意识"],
            "risk_alerts": ["不得包装虚假材料", "不得承诺包过或固定额度"],
            "next_tasks": ["完善企业资料", "修复信用和经营问题", "条件成熟后再诊断"],
        },
    }

    @classmethod
    def generate(
        cls,
        customer: dict[str, Any] | None,
        diagnosis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_diagnosis = diagnosis or {}
        level = str(safe_diagnosis.get("level") or (customer or {}).get("level") or "D").upper()
        if level not in cls.PLAYBOOKS:
            level = "D"
        playbook = cls.PLAYBOOKS[level]
        return {
            "level": level,
            "follow_actions": list(playbook["follow_actions"]),
            "communication_focus": list(playbook["communication_focus"]),
            "risk_alerts": list(playbook["risk_alerts"]),
            "next_tasks": list(playbook["next_tasks"]),
            "first_contact_script": cls._first_contact_script(customer or {}, level),
        }

    @staticmethod
    def _first_contact_script(customer: dict[str, Any], level: str) -> str:
        name = str(customer.get("name") or customer.get("customer_name") or "老板")
        need = str(
            customer.get("financing_need")
            or customer.get("financing_purpose")
            or customer.get("loan_amount")
            or "企业融资"
        )
        return (
            f"{name}您好，我看过您关于“{need}”的初步资料，目前诊断等级为{level}。"
            "我先和您核对经营、流水、负债和资金用途，再判断适合的融资方向；"
            "具体额度、期限和审批结果以银行审核为准。"
        )
