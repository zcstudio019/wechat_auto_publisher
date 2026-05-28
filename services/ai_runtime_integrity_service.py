"""Dashboard service for the read-only AI Runtime integrity center."""

from services.ai_runtime_civilization_service import AIRuntimeCivilizationService
from services.ai_runtime_governance_court_service import AIRuntimeGovernanceCourtService
from services.ai_runtime_integrity_engine import AIRuntimeIntegrityEngine
from services.ai_runtime_judgment_service import AIRuntimeJudgmentService
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeIntegrityService:
    """Build and export Runtime integrity analysis without repairing anything."""

    @classmethod
    def build_integrity_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        civilization_center = dashboard.get("ai_runtime_civilization_center")
        if not civilization_center:
            civilization_center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        governance_court_center = dashboard.get("ai_runtime_governance_court_center")
        if not governance_court_center:
            governance_court_center = AIRuntimeGovernanceCourtService.build_governance_court_center(dashboard)
        judgment_center = dashboard.get("ai_runtime_judgment_center")
        if not judgment_center:
            judgment_center = AIRuntimeJudgmentService.build_judgment_center(dashboard)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)

        return AIRuntimeIntegrityEngine().build_integrity(
            civilization_center,
            governance_court_center,
            judgment_center,
            strategy_center,
            dashboard.get("ai_runtime_decision_center") or {},
            metacognition_center,
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_boundary_center") or {},
        )

    @staticmethod
    def build_integrity_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 完整性中心】",
            f"状态：{center.get('integrity_status') or 'stable'}",
            f"完整性分：{center.get('integrity_score', 0)}",
            f"摘要：{center.get('integrity_summary') or ''}",
            "",
            "完整性问题：",
        ]
        for item in AIRuntimeIntegrityService._integrity_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('risk')} / {item.get('integrity')} / {item.get('recommendation')}"
            )
        if not AIRuntimeIntegrityService._integrity_items(center):
            lines.append("- 暂无 Runtime 完整性问题。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_integrity_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 完整性中心",
            "",
            f"- 状态：{center.get('integrity_status') or 'stable'}",
            f"- 完整性分：{center.get('integrity_score', 0)}",
            f"- 摘要：{center.get('integrity_summary') or ''}",
            "",
            "## 完整性问题",
        ]
        for item in AIRuntimeIntegrityService._integrity_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('risk')} / {item.get('integrity')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not AIRuntimeIntegrityService._integrity_items(center):
            lines.append("- 暂无 Runtime 完整性问题。")
        return "\n".join(lines)

    @staticmethod
    def build_integrity_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeIntegrityService._integrity_items(center or {}):
            rows.append({
                "冲突": item.get("title") or "",
                "类型": item.get("type") or "",
                "风险": item.get("risk") or "",
                "完整性": item.get("integrity") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _integrity_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "consistency_checks",
            "governance_conflicts",
            "civilization_conflicts",
            "strategy_conflicts",
            "automation_boundary_violations",
            "trust_integrity_risks",
            "cognitive_dissonance",
            "value_fragmentations",
        ]:
            items.extend(center.get(key) or [])
        return items
