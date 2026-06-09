"""Runtime action approval center built from read-only Runtime recommendations."""

from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore


class AIRuntimeActionApprovalService:
    """Generate approval queue items and reports without performing actions."""

    @classmethod
    def build_action_approval_center(cls, dashboard: dict | None = None, store: AIRuntimeActionApprovalStore | None = None) -> dict:
        dashboard = dashboard or {}
        store = store or AIRuntimeActionApprovalStore()
        for action in cls._candidate_actions(dashboard):
            store.append_pending_action(action)
        store.expire_old_actions(max_age_days=7)
        approvals = store.read_approvals()
        pending = [item for item in approvals if item.get("status") == "pending"]
        approved = [item for item in approvals if item.get("status") == "approved"]
        rejected = [item for item in approvals if item.get("status") == "rejected"]
        expired = [item for item in approvals if item.get("status") == "expired"]
        high_risk = [item for item in pending if cls._is_high_risk(item)]
        human_required = [item for item in pending if item.get("human_required")]
        status = cls._approval_status(pending, high_risk)

        return {
            "approval_status": status,
            "summary": cls._summary(status, pending, high_risk, human_required),
            "pending_actions": list(reversed(pending))[:50],
            "approved_actions": list(reversed(approved))[:50],
            "rejected_actions": list(reversed(rejected))[:50],
            "expired_actions": list(reversed(expired))[:50],
            "high_risk_pending": list(reversed(high_risk))[:50],
            "human_required_pending": list(reversed(human_required))[:50],
            "approval_recommendations": cls._approval_recommendations(status, high_risk, human_required),
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_action_approval_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 动作审批中心】",
            f"状态：{center.get('approval_status') or 'empty'}",
            f"摘要：{center.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = center.get(key) or []
            if items:
                for item in items[:12]:
                    lines.append(cls._format_item(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_action_approval_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 动作审批中心",
            "",
            f"- 状态：{center.get('approval_status') or 'empty'}",
            f"- 摘要：{center.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = center.get(key) or []
            if items:
                for item in items[:12]:
                    lines.append(cls._format_item(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_action_approval_rows(center: dict | None = None) -> list[dict]:
        rows = []
        seen = set()
        for key in ["pending_actions", "approved_actions", "rejected_actions", "expired_actions"]:
            for item in (center or {}).get(key) or []:
                approval_id = item.get("approval_id") or ""
                if approval_id in seen:
                    continue
                seen.add(approval_id)
                rows.append({
                    "审批ID": approval_id,
                    "动作": item.get("title") or "",
                    "来源": item.get("source") or "",
                    "风险": item.get("risk_level") or "",
                    "状态": item.get("status") or "",
                    "是否人工": str(bool(item.get("human_required"))),
                    "原因": item.get("reason") or "",
                })
        return rows

    @classmethod
    def _candidate_actions(cls, dashboard: dict) -> list[dict]:
        actions = []
        command = dashboard.get("ai_runtime_command_layer") or {}
        for key in ["high_priority_commands", "human_review_commands"]:
            for item in command.get(key) or []:
                actions.append(cls._action_from_item(item, "Command Layer", "command_key", "/ai-dashboard"))

        brief = dashboard.get("ai_runtime_daily_operator_brief") or {}
        for key in ["human_review_today", "must_do_today"]:
            for item in brief.get(key) or []:
                actions.append(cls._action_from_item(item, "Daily Operator Brief", "title", "/ai-dashboard"))

        governance = dashboard.get("ai_runtime_governance_summary") or {}
        for item in governance.get("delegation_risks") or []:
            actions.append(cls._action_from_item(item, "Governance Summary", "risk_key", "/ai-dashboard"))

        capability = dashboard.get("ai_runtime_capability_governance") or {}
        for item in capability.get("approval_required_capabilities") or []:
            actions.append(cls._action_from_item(item, "Capability Governance", "capability_key", "/ai-dashboard"))

        linter = dashboard.get("ai_runtime_policy_linter") or {}
        for item in linter.get("critical_issues") or []:
            actions.append(cls._action_from_item(item, "Policy Linter", "issue_key", "/ai-dashboard"))

        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        for item in release.get("must_fix_before_release") or []:
            actions.append(cls._action_from_item(item, "Release Readiness", "title", "/ai-dashboard/release-readiness"))

        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        if cls._status(ops, "ops_status", "health_status") in {"critical", "failed", "risky"}:
            for item in (ops.get("risk_items") or ops.get("ops_risks") or ops.get("warning_items") or []):
                actions.append(cls._action_from_item(item, "Ops Health", "title", "/ai-dashboard/ops-health"))
        return cls._dedupe(actions)

    @classmethod
    def _action_from_item(cls, item: dict | str, source: str, preferred_key: str, default_route: str) -> dict:
        if not isinstance(item, dict):
            item = {"title": str(item)}
        action_key = item.get(preferred_key) or item.get("action_key") or item.get("command_key") or item.get("capability_key") or item.get("policy_key") or item.get("risk_key") or item.get("title") or "ACTION_REVIEW"
        title = item.get("title") or item.get("capability") or item.get("policy") or item.get("command_key") or action_key
        risk = item.get("risk_level") or item.get("risk") or item.get("priority") or item.get("status") or "medium"
        return {
            "action_key": str(action_key),
            "title": str(title),
            "source": source,
            "risk_level": str(risk).lower(),
            "human_required": bool(item.get("human_required", True)),
            "reason": item.get("reason") or item.get("summary") or item.get("description") or item.get("suggestion") or "",
            "recommended_route": item.get("recommended_route") or item.get("route") or default_route,
        }

    @staticmethod
    def _approval_status(pending: list[dict], high_risk: list[dict]) -> str:
        if any(AIRuntimeActionApprovalService._is_blocking(item) for item in pending):
            return "blocked"
        if high_risk:
            return "blocked"
        if pending:
            return "attention"
        return "empty"

    @staticmethod
    def _is_high_risk(item: dict) -> bool:
        return str(item.get("risk_level") or "").lower() in {"high", "critical", "blocked", "forbidden"}

    @staticmethod
    def _is_blocking(item: dict) -> bool:
        text = " ".join([
            str(item.get("risk_level") or ""),
            str(item.get("status") or ""),
            str(item.get("reason") or ""),
            str(item.get("title") or ""),
        ]).lower()
        return any(token in text for token in ["forbidden", "blocked", "critical"])

    @staticmethod
    def _summary(status: str, pending: list[dict], high_risk: list[dict], human_required: list[dict]) -> str:
        if status == "blocked":
            return f"动作审批队列存在 {len(high_risk)} 条高风险待审批项，仅记录人工审批状态，不执行动作。"
        if status == "attention":
            return f"动作审批队列有 {len(pending)} 条待审批项，其中 {len(human_required)} 条需要人工确认。"
        return "当前暂无待审批 Runtime 动作。"

    @staticmethod
    def _approval_recommendations(status: str, high_risk: list[dict], human_required: list[dict]) -> list[dict]:
        if status == "blocked":
            return [
                {"title": "优先人工复核高风险审批项", "risk_level": "critical", "summary": f"当前高风险待审批 {len(high_risk)} 条。"},
                {"title": "确认审批不代表自动执行", "risk_level": "high", "summary": "approve/reject 只记录 JSON 状态。"},
            ]
        if human_required:
            return [
                {"title": "按人工审批顺序处理 pending 队列", "risk_level": "medium", "summary": f"当前人工待审批 {len(human_required)} 条。"}
            ]
        return [{"title": "保持审批队列为空", "risk_level": "low", "summary": "继续只读观察 Runtime 建议动作。"}]

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "blocked":
            return ["人工查看 high_risk_pending。", "审批记录只更新 JSON，不触发业务动作。"]
        if status == "attention":
            return ["人工查看 pending_actions。", "必要时记录 approve/reject 决策说明。"]
        return ["保持只读审批队列观察。"]

    @staticmethod
    def _format_item(item: dict) -> str:
        return (
            f"- {item.get('approval_id') or ''} / {item.get('title') or ''} / "
            f"{item.get('source') or ''} / {item.get('risk_level') or ''} / "
            f"{item.get('status') or ''}"
        )

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("待审批动作", "pending_actions"),
            ("高风险待审批", "high_risk_pending"),
            ("人工待审批", "human_required_pending"),
            ("已批准记录", "approved_actions"),
            ("已拒绝记录", "rejected_actions"),
            ("已过期记录", "expired_actions"),
        ]

    @staticmethod
    def _status(data: dict, *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value:
                return str(value).lower()
        return ""

    @staticmethod
    def _dedupe(actions: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for action in actions:
            key = (action.get("action_key"), action.get("source"))
            if key in seen:
                continue
            seen.add(key)
            result.append(action)
        return result
