"""Dashboard service for the read-only AI Runtime civilization center."""

from services.ai_runtime_civilization_engine import AIRuntimeCivilizationEngine
from services.ai_runtime_governance_court_service import AIRuntimeGovernanceCourtService
from services.ai_runtime_judgment_service import AIRuntimeJudgmentService
from services.ai_runtime_memory_service import AIRuntimeMemoryService
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeCivilizationService:
    """Build and export Runtime civilization analysis without executing it."""

    @classmethod
    def build_civilization_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        governance_court_center = dashboard.get("ai_runtime_governance_court_center")
        if not governance_court_center:
            governance_court_center = AIRuntimeGovernanceCourtService.build_governance_court_center(dashboard)
        judgment_center = dashboard.get("ai_runtime_judgment_center")
        if not judgment_center:
            judgment_center = AIRuntimeJudgmentService.build_judgment_center(dashboard)
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        memory_center = dashboard.get("ai_runtime_memory_center")
        if not memory_center:
            memory_center = AIRuntimeMemoryService.build_memory_center(dashboard)

        return AIRuntimeCivilizationEngine().build_civilization(
            governance_court_center,
            dashboard.get("ai_runtime_constitution_center") or {},
            judgment_center,
            metacognition_center,
            strategy_center,
            memory_center,
        )

    @staticmethod
    def build_civilization_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 文明中心】",
            f"状态：{center.get('civilization_status') or 'stable'}",
            f"摘要：{center.get('civilization_summary') or ''}",
            "",
            "文明原则：",
        ]
        for item in AIRuntimeCivilizationService._civilization_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('risk')} / {item.get('philosophy')} / {item.get('recommendation')}"
            )
        if not AIRuntimeCivilizationService._civilization_items(center):
            lines.append("- 暂无 Runtime 文明层原则。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_civilization_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 文明中心",
            "",
            f"- 状态：{center.get('civilization_status') or 'stable'}",
            f"- 摘要：{center.get('civilization_summary') or ''}",
            "",
            "## 文明原则",
        ]
        for item in AIRuntimeCivilizationService._civilization_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('risk')}: {item.get('philosophy')} 建议：{item.get('recommendation')}"
            )
        if not AIRuntimeCivilizationService._civilization_items(center):
            lines.append("- 暂无 Runtime 文明层原则。")
        return "\n".join(lines)

    @staticmethod
    def build_civilization_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeCivilizationService._civilization_items(center or {}):
            rows.append({
                "文明原则": item.get("title") or "",
                "类型": item.get("type") or "",
                "风险": item.get("risk") or "",
                "哲学": item.get("philosophy") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _civilization_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "core_values",
            "human_first_principles",
            "civilization_priorities",
            "forbidden_civilization_paths",
            "long_term_survival_principles",
            "governance_philosophies",
            "runtime_identity",
            "civilization_conflicts",
        ]:
            items.extend(center.get(key) or [])
        return items
