"""Dashboard service for the read-only AI Runtime intervention center."""

from services.ai_runtime_causal_graph_service import AIRuntimeCausalGraphService
from services.ai_runtime_intervention_planner import AIRuntimeInterventionPlanner


class AIRuntimeInterventionService:
    """Build and export intervention plans without executing them."""

    @classmethod
    def build_intervention_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        causal_graph = dashboard.get("ai_runtime_causal_graph_center")
        if not causal_graph:
            causal_graph = AIRuntimeCausalGraphService.build_causal_graph_center()

        plan = AIRuntimeInterventionPlanner().plan(causal_graph, dashboard)
        status = cls._status(plan)

        return {
            "intervention_status": status,
            "interventions": plan.get("interventions") or [],
            "root_cause_interventions": plan.get("root_cause_interventions") or [],
            "symptom_interventions": plan.get("symptom_interventions") or [],
            "blocking_interventions": plan.get("blocking_interventions") or [],
            "manual_review_interventions": plan.get("manual_review_interventions") or [],
            "never_auto_interventions": plan.get("never_auto_interventions") or [],
            "intervention_sequence": plan.get("intervention_sequence") or [],
            "pre_checks": plan.get("pre_checks") or [],
            "post_checks": plan.get("post_checks") or [],
            "intervention_summary": plan.get("intervention_summary") or "",
            "recommended_actions": plan.get("recommended_actions") or [],
        }

    @staticmethod
    def build_intervention_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 干预计划中心】",
            f"状态：{center.get('intervention_status') or 'stable'}",
            f"摘要：{center.get('intervention_summary') or ''}",
            "",
            "干预项：",
        ]
        for item in center.get("interventions") or []:
            lines.append(
                f"- {item.get('title')} / {item.get('target')} / "
                f"{item.get('intervention_type')} / {item.get('priority')} / "
                f"auto={item.get('automation_allowed')} / manual={item.get('manual_required')}"
            )
        if not center.get("interventions"):
            lines.append("- 暂无 Runtime 干预计划。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_intervention_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 干预计划中心",
            "",
            f"- 状态：{center.get('intervention_status') or 'stable'}",
            f"- 摘要：{center.get('intervention_summary') or ''}",
            "",
            "## 干预项",
        ]
        for item in center.get("interventions") or []:
            lines.append(
                f"- `{item.get('title')}` -> `{item.get('target')}` "
                f"{item.get('intervention_type')} / {item.get('priority')} / "
                f"automation_allowed={item.get('automation_allowed')} / "
                f"manual_required={item.get('manual_required')}: {item.get('reason')}"
            )
        if not center.get("interventions"):
            lines.append("- 暂无 Runtime 干预计划。")
        return "\n".join(lines)

    @staticmethod
    def build_intervention_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in (center or {}).get("interventions") or []:
            rows.append({
                "干预项": item.get("title") or "",
                "目标": item.get("target") or "",
                "类型": item.get("intervention_type") or "",
                "优先级": item.get("priority") or "",
                "是否允许自动化": str(bool(item.get("automation_allowed"))).lower(),
                "是否需要人工": str(bool(item.get("manual_required"))).lower(),
                "原因": item.get("reason") or "",
            })
        return rows

    @staticmethod
    def _status(plan: dict) -> str:
        critical_root = any(
            item.get("priority") == "critical"
            for item in plan.get("root_cause_interventions") or []
        )
        has_blocking = bool(plan.get("blocking_interventions"))
        if critical_root or has_blocking:
            return "critical"
        if plan.get("root_cause_interventions") or plan.get("symptom_interventions"):
            return "attention"
        return "stable"
