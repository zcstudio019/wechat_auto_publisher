"""Dashboard service for the read-only AI Runtime strategy center."""

from services.ai_runtime_simulation_service import AIRuntimeSimulationService
from services.ai_runtime_strategy_engine import AIRuntimeStrategyEngine


class AIRuntimeStrategyService:
    """Build and export Runtime strategy analysis without executing strategy."""

    @classmethod
    def build_strategy_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        simulation_center = dashboard.get("ai_runtime_simulation_center")
        if not simulation_center:
            simulation_center = AIRuntimeSimulationService.build_simulation_center(dashboard)

        return AIRuntimeStrategyEngine().build_strategy(
            simulation_center,
            dashboard.get("ai_runtime_decision_center") or {},
            dashboard.get("ai_runtime_intervention_center") or {},
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_confidence_center") or {},
            dashboard.get("ai_runtime_task_command_center")
            or dashboard.get("ai_runtime_mission_control_center")
            or {},
        )

    @staticmethod
    def build_strategy_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 战略中心】",
            f"状态：{center.get('strategy_status') or 'stable'}",
            f"摘要：{center.get('strategy_summary') or ''}",
            "",
            "战略：",
        ]
        for item in AIRuntimeStrategyService._strategy_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('priority')} / {item.get('risk')} / {item.get('summary')}"
            )
        if not AIRuntimeStrategyService._strategy_items(center):
            lines.append("- 暂无 Runtime 战略分析。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_strategy_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 战略中心",
            "",
            f"- 状态：{center.get('strategy_status') or 'stable'}",
            f"- 摘要：{center.get('strategy_summary') or ''}",
            "",
            "## 战略",
        ]
        for item in AIRuntimeStrategyService._strategy_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('priority')} / {item.get('risk')}: {item.get('summary')}"
            )
        if not AIRuntimeStrategyService._strategy_items(center):
            lines.append("- 暂无 Runtime 战略分析。")
        return "\n".join(lines)

    @staticmethod
    def build_strategy_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeStrategyService._strategy_items(center or {}):
            rows.append({
                "战略": item.get("title") or "",
                "类型": item.get("type") or "",
                "优先级": item.get("priority") or "",
                "风险": item.get("risk") or "",
                "摘要": item.get("summary") or "",
            })
        return rows

    @staticmethod
    def _strategy_items(center: dict) -> list[dict]:
        items = []
        items.extend(center.get("short_term_strategies") or [])
        items.extend(center.get("mid_term_strategies") or [])
        items.extend(center.get("long_term_strategies") or [])
        for item in center.get("technical_debt_risks") or []:
            items.append({
                "title": item.get("title") or "",
                "type": "technical_debt",
                "priority": item.get("severity") or "",
                "risk": item.get("title") or "",
                "summary": item.get("summary") or "",
            })
        for item in center.get("capability_priorities") or []:
            items.append({
                "title": item.get("capability") or "",
                "type": "capability",
                "priority": item.get("priority") or "",
                "risk": "capability gap",
                "summary": item.get("summary") or "",
            })
        return items
