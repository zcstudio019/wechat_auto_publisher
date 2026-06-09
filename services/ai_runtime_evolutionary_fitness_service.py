"""Dashboard service for the read-only AI Runtime evolutionary fitness center."""

from services.ai_runtime_adaptive_service import AIRuntimeAdaptiveService
from services.ai_runtime_civilization_service import AIRuntimeCivilizationService
from services.ai_runtime_evolutionary_fitness_engine import AIRuntimeEvolutionaryFitnessEngine
from services.ai_runtime_governance_court_service import AIRuntimeGovernanceCourtService
from services.ai_runtime_immune_service import AIRuntimeImmuneService
from services.ai_runtime_integrity_service import AIRuntimeIntegrityService
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_resilience_service import AIRuntimeResilienceService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeEvolutionaryFitnessService:
    """Build and export Runtime evolutionary fitness analysis without淘汰."""

    @classmethod
    def build_evolutionary_fitness_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        adaptive_center = dashboard.get("ai_runtime_adaptive_center")
        if not adaptive_center:
            adaptive_center = AIRuntimeAdaptiveService.build_adaptive_center(dashboard)
        resilience_center = dashboard.get("ai_runtime_resilience_center")
        if not resilience_center:
            resilience_center = AIRuntimeResilienceService.build_resilience_center(dashboard)
        civilization_center = dashboard.get("ai_runtime_civilization_center")
        if not civilization_center:
            civilization_center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        integrity_center = dashboard.get("ai_runtime_integrity_center")
        if not integrity_center:
            integrity_center = AIRuntimeIntegrityService.build_integrity_center(dashboard)
        immune_center = dashboard.get("ai_runtime_immune_center")
        if not immune_center:
            immune_center = AIRuntimeImmuneService.build_immune_center(dashboard)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        governance_court_center = dashboard.get("ai_runtime_governance_court_center")
        if not governance_court_center:
            governance_court_center = AIRuntimeGovernanceCourtService.build_governance_court_center(dashboard)
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)

        return AIRuntimeEvolutionaryFitnessEngine().build_fitness_analysis(
            adaptive_center,
            resilience_center,
            civilization_center,
            integrity_center,
            immune_center,
            strategy_center,
            governance_court_center,
            metacognition_center,
        )

    @staticmethod
    def build_evolutionary_fitness_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 演化适应度中心】",
            f"状态：{center.get('fitness_status') or 'unstable evolution'}",
            f"适应度分：{center.get('fitness_score', 0)}",
            f"摘要：{center.get('evolutionary_summary') or ''}",
            "",
            "演化适应度分析：",
        ]
        items = AIRuntimeEvolutionaryFitnessService._fitness_items(center)
        for item in items:
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('fitness_level')} / {item.get('risk')} / {item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 演化适应度风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_evolutionary_fitness_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 演化适应度中心",
            "",
            f"- 状态：{center.get('fitness_status') or 'unstable evolution'}",
            f"- 适应度分：{center.get('fitness_score', 0)}",
            f"- 摘要：{center.get('evolutionary_summary') or ''}",
            "",
            "## 演化适应度分析",
        ]
        items = AIRuntimeEvolutionaryFitnessService._fitness_items(center)
        for item in items:
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('fitness_level')} / {item.get('risk')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 演化适应度风险。")
        return "\n".join(lines)

    @staticmethod
    def build_evolutionary_fitness_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeEvolutionaryFitnessService._fitness_items(center or {}):
            rows.append({
                "结构": item.get("title") or "",
                "类型": item.get("type") or "",
                "适应度": item.get("fitness_level") or "",
                "风险": item.get("risk") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _fitness_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "high_fitness_structures",
            "low_fitness_structures",
            "survival_advantages",
            "evolutionary_risks",
            "obsolete_patterns",
            "long_term_adaptive_patterns",
            "civilization_survival_patterns",
            "extinction_risks",
            "selection_pressures",
        ]:
            items.extend(center.get(key) or [])
        return items
