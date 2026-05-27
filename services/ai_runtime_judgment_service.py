"""Dashboard service for the read-only AI Runtime judgment center."""

from services.ai_runtime_judgment_engine import AIRuntimeJudgmentEngine
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeJudgmentService:
    """Build and export Runtime judgment analysis without executing judgment."""

    @classmethod
    def build_judgment_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)

        return AIRuntimeJudgmentEngine().build_judgment(
            metacognition_center,
            strategy_center,
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_confidence_center") or {},
            dashboard.get("ai_runtime_constitution_center") or {},
            dashboard.get("ai_runtime_boundary_center") or {},
            dashboard.get("ai_runtime_policy_gate_center") or {},
        )

    @staticmethod
    def build_judgment_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 判断中心】",
            f"状态：{center.get('judgment_status') or 'stable'}",
            f"摘要：{center.get('judgment_summary') or ''}",
            "",
            "判断：",
        ]
        for item in AIRuntimeJudgmentService._judgment_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('risk')} / {item.get('judgment')} / {item.get('recommendation')}"
            )
        if not AIRuntimeJudgmentService._judgment_items(center):
            lines.append("- 暂无 Runtime 判断风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_judgment_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 判断中心",
            "",
            f"- 状态：{center.get('judgment_status') or 'stable'}",
            f"- 摘要：{center.get('judgment_summary') or ''}",
            "",
            "## 判断",
        ]
        for item in AIRuntimeJudgmentService._judgment_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('risk')}: {item.get('judgment')} 建议：{item.get('recommendation')}"
            )
        if not AIRuntimeJudgmentService._judgment_items(center):
            lines.append("- 暂无 Runtime 判断风险。")
        return "\n".join(lines)

    @staticmethod
    def build_judgment_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeJudgmentService._judgment_items(center or {}):
            rows.append({
                "问题": item.get("title") or "",
                "类型": item.get("type") or "",
                "风险": item.get("risk") or "",
                "判断": item.get("judgment") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _judgment_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "acceptable_risks",
            "unacceptable_risks",
            "dangerous_automations",
            "human_only_domains",
            "unsafe_high_confidence_items",
            "ethical_conflicts",
            "governance_violations",
            "long_term_rejections",
        ]:
            items.extend(center.get(key) or [])
        return items
