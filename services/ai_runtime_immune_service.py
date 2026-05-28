"""Dashboard service for the read-only AI Runtime immune system center."""

from services.ai_runtime_civilization_service import AIRuntimeCivilizationService
from services.ai_runtime_governance_court_service import AIRuntimeGovernanceCourtService
from services.ai_runtime_immune_engine import AIRuntimeImmuneEngine
from services.ai_runtime_integrity_service import AIRuntimeIntegrityService
from services.ai_runtime_judgment_service import AIRuntimeJudgmentService
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService


class AIRuntimeImmuneService:
    """Build and export Runtime immune analysis without executing defenses."""

    @classmethod
    def build_immune_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        integrity_center = dashboard.get("ai_runtime_integrity_center")
        if not integrity_center:
            integrity_center = AIRuntimeIntegrityService.build_integrity_center(dashboard)
        civilization_center = dashboard.get("ai_runtime_civilization_center")
        if not civilization_center:
            civilization_center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        governance_court_center = dashboard.get("ai_runtime_governance_court_center")
        if not governance_court_center:
            governance_court_center = AIRuntimeGovernanceCourtService.build_governance_court_center(dashboard)
        judgment_center = dashboard.get("ai_runtime_judgment_center")
        if not judgment_center:
            judgment_center = AIRuntimeJudgmentService.build_judgment_center(dashboard)
        metacognition_center = dashboard.get("ai_runtime_metacognition_center")
        if not metacognition_center:
            metacognition_center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)
        signal_center = dashboard.get("ai_runtime_signal_intelligence")
        if not signal_center:
            signal_center = AIRuntimeSignalIntelligenceService.build_signal_intelligence()

        return AIRuntimeImmuneEngine().build_immune_analysis(
            integrity_center,
            civilization_center,
            governance_court_center,
            judgment_center,
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_boundary_center") or {},
            metacognition_center,
            signal_center,
        )

    @staticmethod
    def build_immune_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 免疫系统中心】",
            f"状态：{center.get('immune_status') or 'stable'}",
            f"免疫健康分：{center.get('immune_health_score', 0)}",
            f"摘要：{center.get('immune_summary') or ''}",
            "",
            "免疫风险：",
        ]
        items = AIRuntimeImmuneService._immune_items(center)
        for item in items:
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('immune_level')} / {item.get('collapse_risk')} / {item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 免疫风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_immune_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 免疫系统中心",
            "",
            f"- 状态：{center.get('immune_status') or 'stable'}",
            f"- 免疫健康分：{center.get('immune_health_score', 0)}",
            f"- 摘要：{center.get('immune_summary') or ''}",
            "",
            "## 免疫风险",
        ]
        items = AIRuntimeImmuneService._immune_items(center)
        for item in items:
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('immune_level')} / {item.get('collapse_risk')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not items:
            lines.append("- 暂无 Runtime 免疫风险。")
        return "\n".join(lines)

    @staticmethod
    def build_immune_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeImmuneService._immune_items(center or {}):
            rows.append({
                "风险": item.get("title") or "",
                "类型": item.get("type") or "",
                "免疫等级": item.get("immune_level") or "",
                "崩塌风险": item.get("collapse_risk") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _immune_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "systemic_risks",
            "governance_corruption_risks",
            "civilization_regression_risks",
            "integrity_collapse_risks",
            "dangerous_automation_patterns",
            "trust_decay_patterns",
            "fragility_patterns",
            "high_risk_mutations",
            "immune_alerts",
        ]:
            items.extend(center.get(key) or [])
        return items
