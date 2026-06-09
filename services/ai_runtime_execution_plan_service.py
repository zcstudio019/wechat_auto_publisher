"""Build execution plans from approved Runtime action records only."""

from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore


class AIRuntimeExecutionPlanService:
    """Create human-readable plans without performing any approved action."""

    @classmethod
    def build_execution_plan_center(cls, dashboard: dict | None = None, store: AIRuntimeActionApprovalStore | None = None) -> dict:
        store = store or AIRuntimeActionApprovalStore()
        approved_actions = [
            item for item in store.read_approvals()
            if item.get("status") == "approved"
        ]
        plans = [cls._build_plan(item) for item in approved_actions]
        high_risk = [plan for plan in plans if plan.get("risk_level") in {"high", "critical", "forbidden", "blocked"}]
        human_review = [plan for plan in plans if plan.get("human_review")]
        rollback = [plan for plan in plans if plan.get("rollback_steps")]
        verification = [plan for plan in plans if plan.get("verification_steps")]
        status = cls._plan_status(plans, high_risk, human_review)

        return {
            "plan_status": status,
            "pending_plan_count": len(plans),
            "execution_plans": plans,
            "high_risk_plans": high_risk,
            "human_review_required": human_review,
            "rollback_required": rollback,
            "verification_required": verification,
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_execution_plan_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 动作执行计划中心】",
            f"状态：{center.get('plan_status') or 'empty'}",
            f"计划数：{center.get('pending_plan_count') or 0}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = center.get(key) or []
            if items:
                for item in items[:12]:
                    lines.append(cls._format_plan(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_execution_plan_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 动作执行计划中心",
            "",
            f"- 状态：{center.get('plan_status') or 'empty'}",
            f"- 计划数：{center.get('pending_plan_count') or 0}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = center.get(key) or []
            if items:
                for item in items[:12]:
                    lines.append(cls._format_plan(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_execution_plan_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for plan in (center or {}).get("execution_plans") or []:
            rows.append({
                "审批ID": plan.get("approval_id") or "",
                "动作": plan.get("title") or "",
                "风险": plan.get("risk_level") or "",
                "步骤": " | ".join(plan.get("steps") or []),
                "验证": " | ".join(plan.get("verification_steps") or []),
                "回滚": " | ".join(plan.get("rollback_steps") or []),
            })
        return rows

    @classmethod
    def _build_plan(cls, action: dict) -> dict:
        risk = str(action.get("risk_level") or "medium").lower()
        title = action.get("title") or action.get("action_key") or "Approved Runtime action"
        source = action.get("source") or "Action Approval"
        return {
            "approval_id": action.get("approval_id") or "",
            "action_key": action.get("action_key") or "",
            "title": title,
            "risk_level": risk,
            "steps": cls._steps(title, source, action),
            "verification_steps": cls._verification_steps(title, source, action),
            "rollback_steps": cls._rollback_steps(title, source, action),
            "human_review": bool(action.get("human_required", True)),
            "estimated_impact": cls._estimated_impact(risk, source),
            "status": "planned",
        }

    @staticmethod
    def _steps(title: str, source: str, action: dict) -> list[str]:
        route = action.get("recommended_route") or "/ai-dashboard"
        return [
            f"人工打开建议入口：{route}",
            f"核对审批动作来源：{source}",
            f"阅读动作原因：{action.get('reason') or title}",
            "由负责人在原业务页面手动处理，计划中心不触发任何动作。",
        ]

    @staticmethod
    def _verification_steps(title: str, source: str, action: dict) -> list[str]:
        return [
            "复查 Action Approval Center 中审批记录仍为 approved。",
            "复查 Ops Health、Release Readiness 或相关来源页面状态。",
            "确认没有自动审核、自动发布或自动恢复被触发。",
        ]

    @staticmethod
    def _rollback_steps(title: str, source: str, action: dict) -> list[str]:
        return [
            "如人工处理结果不符合预期，先停止继续推进后续人工步骤。",
            "回到原业务页面按既有人工流程撤回或恢复，不由本中心处理。",
            "在审批记录 decision_note 中补充人工回退说明。",
        ]

    @staticmethod
    def _estimated_impact(risk: str, source: str) -> str:
        if risk in {"critical", "forbidden", "blocked"}:
            return f"{source} high governance impact; requires strict human coordination."
        if risk == "high":
            return f"{source} operational impact; requires human review before any manual handling."
        return f"{source} limited impact; keep verification and rollback notes ready."

    @staticmethod
    def _plan_status(plans: list[dict], high_risk: list[dict], human_review: list[dict]) -> str:
        if not plans:
            return "empty"
        if any(plan.get("risk_level") in {"critical", "forbidden", "blocked"} or AIRuntimeExecutionPlanService._is_human_only(plan) for plan in plans):
            return "blocked"
        if high_risk or human_review:
            return "attention"
        return "planned"

    @staticmethod
    def _is_human_only(plan: dict) -> bool:
        text = " ".join([
            str(plan.get("title") or ""),
            str(plan.get("action_key") or ""),
            str(plan.get("estimated_impact") or ""),
        ]).lower()
        return "human-only" in text or "human only" in text

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "blocked":
            return ["先人工复核 blocked/high risk 计划。", "确认本中心仅提供计划，不处理业务动作。"]
        if status == "attention":
            return ["逐条检查 human_review_required。", "执行前准备验证项和回滚说明。"]
        if status == "planned":
            return ["按 execution_plans 逐条人工阅读。", "执行前仍需人工确认。"]
        return ["暂无 approved action，无需生成执行计划。"]

    @staticmethod
    def _format_plan(plan: dict) -> str:
        return (
            f"- {plan.get('approval_id') or ''} / {plan.get('title') or ''} / "
            f"{plan.get('risk_level') or ''} / {plan.get('status') or 'planned'}"
        )

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("执行计划", "execution_plans"),
            ("高风险计划", "high_risk_plans"),
            ("人工复核计划", "human_review_required"),
            ("需要回滚方案", "rollback_required"),
            ("需要验证方案", "verification_required"),
        ]
