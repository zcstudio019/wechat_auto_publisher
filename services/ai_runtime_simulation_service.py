"""Dashboard service for the read-only AI Runtime simulation center."""

from services.ai_runtime_decision_service import AIRuntimeDecisionService
from services.ai_runtime_simulation_engine import AIRuntimeSimulationEngine


class AIRuntimeSimulationService:
    """Build and export Runtime simulations without executing outcomes."""

    @classmethod
    def build_simulation_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        decision_center = dashboard.get("ai_runtime_decision_center")
        if not decision_center:
            decision_center = AIRuntimeDecisionService.build_decision_center(dashboard)

        result = AIRuntimeSimulationEngine().simulate(
            decision_center.get("decisions") or [],
            dashboard.get("ai_runtime_causal_graph_center") or {},
            dashboard.get("ai_runtime_intervention_center") or {},
            dashboard.get("ai_runtime_signal_intelligence") or {},
        )
        status = cls._status(result)

        return {
            "simulation_status": status,
            "simulations": result.get("simulations") or [],
            "best_case_scenarios": result.get("best_case_scenarios") or [],
            "worst_case_scenarios": result.get("worst_case_scenarios") or [],
            "risk_propagation_forecasts": result.get("risk_propagation_forecasts") or [],
            "rollback_impacts": result.get("rollback_impacts") or [],
            "simulation_summary": result.get("simulation_summary") or "",
            "recommended_actions": result.get("recommended_actions") or [],
        }

    @staticmethod
    def build_simulation_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 模拟推演中心】",
            f"状态：{center.get('simulation_status') or 'stable'}",
            f"摘要：{center.get('simulation_summary') or ''}",
            "",
            "模拟推演：",
        ]
        for item in center.get("simulations") or []:
            lines.append(
                f"- {item.get('title')} / {item.get('simulation_type')} / "
                f"{item.get('risk_level')} / {item.get('stability_change')} / "
                f"rollback={item.get('rollback_available')} / {item.get('summary')}"
            )
        if not center.get("simulations"):
            lines.append("- 暂无 Runtime 模拟推演。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_simulation_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 模拟推演中心",
            "",
            f"- 状态：{center.get('simulation_status') or 'stable'}",
            f"- 摘要：{center.get('simulation_summary') or ''}",
            "",
            "## 模拟推演",
        ]
        for item in center.get("simulations") or []:
            lines.append(
                f"- `{item.get('title')}` {item.get('simulation_type')} / "
                f"{item.get('risk_level')} / {item.get('stability_change')}: {item.get('summary')}"
            )
        if not center.get("simulations"):
            lines.append("- 暂无 Runtime 模拟推演。")
        return "\n".join(lines)

    @staticmethod
    def build_simulation_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in (center or {}).get("simulations") or []:
            rows.append({
                "模拟": item.get("title") or "",
                "类型": item.get("simulation_type") or "",
                "风险等级": item.get("risk_level") or "",
                "稳定性变化": item.get("stability_change") or "",
                "rollback 可用": str(bool(item.get("rollback_available"))).lower(),
                "摘要": item.get("summary") or "",
            })
        return rows

    @staticmethod
    def _status(result: dict) -> str:
        critical_forecast = any(
            item.get("risk_level") == "critical"
            for item in result.get("risk_propagation_forecasts") or []
        )
        if critical_forecast or result.get("worst_case_scenarios"):
            return "critical"
        if result.get("simulations"):
            return "attention"
        return "stable"
