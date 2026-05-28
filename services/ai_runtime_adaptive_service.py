"""Dashboard service for the read-only AI Runtime adaptive system center."""

from services.ai_runtime_adaptive_engine import AIRuntimeAdaptiveEngine
from services.ai_runtime_civilization_service import AIRuntimeCivilizationService
from services.ai_runtime_immune_service import AIRuntimeImmuneService
from services.ai_runtime_integrity_service import AIRuntimeIntegrityService
from services.ai_runtime_memory_service import AIRuntimeMemoryService
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeAdaptiveService:
    """Build and export Runtime adaptive analysis without adapting Runtime."""

    @classmethod
    def build_adaptive_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        civilization_center = dashboard.get("ai_runtime_civilization_center")
        if not civilization_center:
            civilization_center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        integrity_center = dashboard.get("ai_runtime_integrity_center")
        if not integrity_center:
            integrity_center = AIRuntimeIntegrityService.build_integrity_center(dashboard)
        immune_center = dashboard.get("ai_runtime_immune_center")
        if not immune_center:
            immune_center = AIRuntimeImmuneService.build_immune_center(dashboard)
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)
        memory_center = dashboard.get("ai_runtime_memory_center")
        if not memory_center:
            memory_center = AIRuntimeMemoryService.build_memory_center(dashboard)
        signal_center = dashboard.get("ai_runtime_signal_intelligence")
        if not signal_center:
            signal_center = AIRuntimeSignalIntelligenceService.build_signal_intelligence()

        return AIRuntimeAdaptiveEngine().build_adaptive_analysis(
            strategy_center,
            civilization_center,
            integrity_center,
            immune_center,
            metacognition_center,
            memory_center,
            dashboard.get("ai_runtime_forecast_center") or {},
            signal_center,
        )

    @staticmethod
    def build_adaptive_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 自适应系统中心】",
            f"状态：{center.get('adaptive_status') or 'adaptive'}",
            f"适应分：{center.get('adaptation_score', 0)}",
            f"摘要：{center.get('adaptive_summary') or ''}",
            "",
            "自适应分析：",
        ]
        items = AIRuntimeAdaptiveService._adaptive_items(center)
        for item in items:
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('evolutionary_pressure')} / {item.get('risk')} / {item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 自适应风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_adaptive_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 自适应系统中心",
            "",
            f"- 状态：{center.get('adaptive_status') or 'adaptive'}",
            f"- 适应分：{center.get('adaptation_score', 0)}",
            f"- 摘要：{center.get('adaptive_summary') or ''}",
            "",
            "## 自适应分析",
        ]
        items = AIRuntimeAdaptiveService._adaptive_items(center)
        for item in items:
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('evolutionary_pressure')} / {item.get('risk')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 自适应风险。")
        return "\n".join(lines)

    @staticmethod
    def build_adaptive_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeAdaptiveService._adaptive_items(center or {}):
            rows.append({
                "适应项": item.get("title") or "",
                "类型": item.get("type") or "",
                "演化压力": item.get("evolutionary_pressure") or "",
                "风险": item.get("risk") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _adaptive_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "environment_change_signals",
            "aging_governance_patterns",
            "strategic_obsolescence_risks",
            "civilization_rigidity_risks",
            "cognitive_stagnation_patterns",
            "long_term_survival_risks",
            "required_adaptations",
            "evolutionary_pressures",
        ]:
            items.extend(center.get(key) or [])
        return items
