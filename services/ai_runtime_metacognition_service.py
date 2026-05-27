"""Dashboard service for the read-only AI Runtime meta-cognition center."""

from services.ai_runtime_decision_service import AIRuntimeDecisionService
from services.ai_runtime_memory_service import AIRuntimeMemoryService
from services.ai_runtime_metacognition_engine import AIRuntimeMetaCognitionEngine
from services.ai_runtime_simulation_service import AIRuntimeSimulationService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeMetaCognitionService:
    """Build and export Runtime self-awareness analysis without executing actions."""

    @classmethod
    def build_metacognition_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        memory_center = dashboard.get("ai_runtime_memory_center")
        if not memory_center:
            memory_center = AIRuntimeMemoryService.build_memory_center(dashboard)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        decision_center = dashboard.get("ai_runtime_decision_center")
        if not decision_center:
            decision_center = AIRuntimeDecisionService.build_decision_center(dashboard)
        simulation_center = dashboard.get("ai_runtime_simulation_center")
        if not simulation_center:
            simulation_center = AIRuntimeSimulationService.build_simulation_center(dashboard)

        return AIRuntimeMetaCognitionEngine().build_metacognition(
            memory_center,
            strategy_center,
            decision_center,
            simulation_center,
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_confidence_center") or {},
        )

    @staticmethod
    def build_metacognition_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 元认知中心】",
            f"状态：{center.get('metacognition_status') or 'stable'}",
            f"摘要：{center.get('self_awareness_summary') or ''}",
            "",
            "问题：",
        ]
        for item in AIRuntimeMetaCognitionService._metacognition_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('risk')} / {item.get('summary')} / {item.get('recommendation')}"
            )
        if not AIRuntimeMetaCognitionService._metacognition_items(center):
            lines.append("- 暂无 Runtime 元认知风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_metacognition_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 元认知中心",
            "",
            f"- 状态：{center.get('metacognition_status') or 'stable'}",
            f"- 摘要：{center.get('self_awareness_summary') or ''}",
            "",
            "## 问题",
        ]
        for item in AIRuntimeMetaCognitionService._metacognition_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('risk')}: {item.get('summary')} 建议：{item.get('recommendation')}"
            )
        if not AIRuntimeMetaCognitionService._metacognition_items(center):
            lines.append("- 暂无 Runtime 元认知风险。")
        return "\n".join(lines)

    @staticmethod
    def build_metacognition_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeMetaCognitionService._metacognition_items(center or {}):
            rows.append({
                "问题": item.get("title") or "",
                "类型": item.get("type") or "",
                "风险": item.get("risk") or "",
                "摘要": item.get("summary") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _metacognition_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "blind_spots",
            "uncertainty_sources",
            "overconfidence_risks",
            "governance_gaps",
            "strategic_biases",
            "fragile_assumptions",
            "cognitive_conflicts",
        ]:
            items.extend(center.get(key) or [])
        return items
