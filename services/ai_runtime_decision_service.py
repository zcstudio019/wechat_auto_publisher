"""Dashboard service for the read-only AI Runtime decision center."""

from services.ai_runtime_decision_engine import AIRuntimeDecisionEngine
from services.ai_runtime_intervention_service import AIRuntimeInterventionService


class AIRuntimeDecisionService:
    """Build and export Runtime decision recommendations without executing them."""

    @classmethod
    def build_decision_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        intervention_center = dashboard.get("ai_runtime_intervention_center")
        if not intervention_center:
            intervention_center = AIRuntimeInterventionService.build_intervention_center(dashboard)

        result = AIRuntimeDecisionEngine().build_decisions(
            intervention_center,
            dashboard.get("ai_runtime_causal_graph_center") or {},
            dashboard.get("ai_runtime_policy_gate_center") or {},
            dashboard.get("ai_runtime_constitution_center") or {},
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_confidence_center") or {},
        )
        status = cls._status(result)

        return {
            "decision_status": status,
            "decisions": result.get("decisions") or [],
            "recommended_decisions": result.get("recommended_decisions") or [],
            "blocked_decisions": result.get("blocked_decisions") or [],
            "manual_only_decisions": result.get("manual_only_decisions") or [],
            "high_risk_decisions": result.get("high_risk_decisions") or [],
            "rollback_candidates": result.get("rollback_candidates") or [],
            "decision_summary": result.get("decision_summary") or "",
            "recommended_actions": result.get("recommended_actions") or [],
        }

    @staticmethod
    def build_decision_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 决策中心】",
            f"状态：{center.get('decision_status') or 'stable'}",
            f"摘要：{center.get('decision_summary') or ''}",
            "",
            "决策建议：",
        ]
        for item in center.get("decisions") or []:
            lines.append(
                f"- {item.get('title')} / {item.get('decision_type')} / "
                f"{item.get('decision_status')} / {item.get('confidence')} / {item.get('risk')}"
            )
        if not center.get("decisions"):
            lines.append("- 暂无 Runtime 决策建议。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_decision_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 决策中心",
            "",
            f"- 状态：{center.get('decision_status') or 'stable'}",
            f"- 摘要：{center.get('decision_summary') or ''}",
            "",
            "## 决策建议",
        ]
        for item in center.get("decisions") or []:
            lines.append(
                f"- `{item.get('title')}` {item.get('decision_type')} / "
                f"{item.get('decision_status')} / {item.get('confidence')}: {item.get('risk')}"
            )
        if not center.get("decisions"):
            lines.append("- 暂无 Runtime 决策建议。")
        return "\n".join(lines)

    @staticmethod
    def build_decision_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in (center or {}).get("decisions") or []:
            rows.append({
                "决策": item.get("title") or "",
                "类型": item.get("decision_type") or "",
                "状态": item.get("decision_status") or "",
                "信心": item.get("confidence") or "",
                "风险": item.get("risk") or "",
                "回退方案": item.get("rollback_plan") or "",
            })
        return rows

    @staticmethod
    def _status(result: dict) -> str:
        if result.get("blocked_decisions") or result.get("high_risk_decisions"):
            return "critical"
        if result.get("manual_only_decisions"):
            return "attention"
        return "stable"
