"""Dashboard service for the read-only AI Runtime resilience system center."""

from services.ai_runtime_adaptive_service import AIRuntimeAdaptiveService
from services.ai_runtime_civilization_service import AIRuntimeCivilizationService
from services.ai_runtime_immune_service import AIRuntimeImmuneService
from services.ai_runtime_integrity_service import AIRuntimeIntegrityService
from services.ai_runtime_intervention_service import AIRuntimeInterventionService
from services.ai_runtime_memory_service import AIRuntimeMemoryService
from services.ai_runtime_resilience_engine import AIRuntimeResilienceEngine
from services.ai_runtime_simulation_service import AIRuntimeSimulationService


class AIRuntimeResilienceService:
    """Build and export Runtime resilience analysis without executing recovery."""

    @classmethod
    def build_resilience_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        immune_center = dashboard.get("ai_runtime_immune_center")
        if not immune_center:
            immune_center = AIRuntimeImmuneService.build_immune_center(dashboard)
        adaptive_center = dashboard.get("ai_runtime_adaptive_center")
        if not adaptive_center:
            adaptive_center = AIRuntimeAdaptiveService.build_adaptive_center(dashboard)
        integrity_center = dashboard.get("ai_runtime_integrity_center")
        if not integrity_center:
            integrity_center = AIRuntimeIntegrityService.build_integrity_center(dashboard)
        civilization_center = dashboard.get("ai_runtime_civilization_center")
        if not civilization_center:
            civilization_center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        intervention_center = dashboard.get("ai_runtime_intervention_center")
        if not intervention_center:
            intervention_center = AIRuntimeInterventionService.build_intervention_center(dashboard)
        simulation_center = dashboard.get("ai_runtime_simulation_center")
        if not simulation_center:
            simulation_center = AIRuntimeSimulationService.build_simulation_center(dashboard)
        memory_center = dashboard.get("ai_runtime_memory_center")
        if not memory_center:
            memory_center = AIRuntimeMemoryService.build_memory_center(dashboard)

        return AIRuntimeResilienceEngine().build_resilience_analysis(
            immune_center,
            adaptive_center,
            integrity_center,
            civilization_center,
            dashboard.get("ai_runtime_forecast_center") or {},
            intervention_center,
            simulation_center,
            memory_center,
        )

    @staticmethod
    def build_resilience_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 韧性系统中心】",
            f"状态：{center.get('resilience_status') or 'fragile'}",
            f"韧性分：{center.get('resilience_score', 0)}",
            f"展望：{center.get('long_term_resilience_outlook') or ''}",
            "",
            "韧性分析：",
        ]
        items = AIRuntimeResilienceService._resilience_items(center)
        for item in items:
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('resilience_level')} / {item.get('risk')} / {item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 韧性风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_resilience_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 韧性系统中心",
            "",
            f"- 状态：{center.get('resilience_status') or 'fragile'}",
            f"- 韧性分：{center.get('resilience_score', 0)}",
            f"- 展望：{center.get('long_term_resilience_outlook') or ''}",
            "",
            "## 韧性分析",
        ]
        items = AIRuntimeResilienceService._resilience_items(center)
        for item in items:
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('resilience_level')} / {item.get('risk')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 韧性风险。")
        return "\n".join(lines)

    @staticmethod
    def build_resilience_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeResilienceService._resilience_items(center or {}):
            rows.append({
                "韧性项": item.get("title") or "",
                "类型": item.get("type") or "",
                "韧性等级": item.get("resilience_level") or "",
                "风险": item.get("risk") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _resilience_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "recovery_capabilities",
            "fragility_patterns",
            "robustness_patterns",
            "resilience_patterns",
            "antifragile_patterns",
            "collapse_risks",
            "irreversible_failure_risks",
            "stress_response_patterns",
        ]:
            items.extend(center.get(key) or [])
        return items
