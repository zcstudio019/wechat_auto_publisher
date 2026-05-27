"""Dashboard service for the read-only AI Runtime governance court center."""

from services.ai_runtime_governance_court_engine import AIRuntimeGovernanceCourtEngine
from services.ai_runtime_judgment_service import AIRuntimeJudgmentService


class AIRuntimeGovernanceCourtService:
    """Build and export final governance court analysis without enforcing rulings."""

    @classmethod
    def build_governance_court_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        judgment_center = dashboard.get("ai_runtime_judgment_center")
        if not judgment_center:
            judgment_center = AIRuntimeJudgmentService.build_judgment_center(dashboard)

        return AIRuntimeGovernanceCourtEngine().build_governance_court(
            judgment_center,
            dashboard.get("ai_runtime_constitution_center") or {},
            dashboard.get("ai_runtime_boundary_center") or {},
            dashboard.get("ai_runtime_policy_gate_center") or {},
            dashboard.get("ai_runtime_trust_center") or {},
            dashboard.get("ai_runtime_delegation_center")
            or dashboard.get("ai_runtime_task_command_center")
            or dashboard.get("ai_runtime_mission_control_center")
            or {},
        )

    @staticmethod
    def build_governance_court_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 治理法庭中心】",
            f"状态：{center.get('court_status') or 'stable'}",
            f"摘要：{center.get('court_summary') or ''}",
            "",
            "裁决：",
        ]
        for item in AIRuntimeGovernanceCourtService._court_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('ruling')} / {item.get('risk')} / {item.get('recommendation')}"
            )
        if not AIRuntimeGovernanceCourtService._court_items(center):
            lines.append("- 暂无 Runtime 治理法庭裁决。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_governance_court_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 治理法庭中心",
            "",
            f"- 状态：{center.get('court_status') or 'stable'}",
            f"- 摘要：{center.get('court_summary') or ''}",
            "",
            "## 裁决",
        ]
        for item in AIRuntimeGovernanceCourtService._court_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('ruling')} / {item.get('risk')}: {item.get('summary')} "
                f"建议：{item.get('recommendation')}"
            )
        if not AIRuntimeGovernanceCourtService._court_items(center):
            lines.append("- 暂无 Runtime 治理法庭裁决。")
        return "\n".join(lines)

    @staticmethod
    def build_governance_court_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeGovernanceCourtService._court_items(center or {}):
            rows.append({
                "领域": item.get("title") or "",
                "类型": item.get("type") or "",
                "裁决": item.get("ruling") or "",
                "风险": item.get("risk") or "",
                "建议": item.get("recommendation") or "",
            })
        return rows

    @staticmethod
    def _court_items(center: dict) -> list[dict]:
        items = []
        for key in [
            "allowed_domains",
            "restricted_domains",
            "forbidden_domains",
            "human_sovereignty_domains",
            "court_rulings",
            "constitutional_conflicts",
            "governance_overrides",
            "permanent_prohibitions",
        ]:
            items.extend(center.get(key) or [])
        return items
