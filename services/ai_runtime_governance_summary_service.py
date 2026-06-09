"""Read-only AI Runtime governance summary center."""


class AIRuntimeGovernanceSummaryService:
    """Compress high-level governance signals into an executive summary."""

    @classmethod
    def build_governance_summary(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        capability_matrix = dashboard.get("ai_runtime_capability_matrix") or {}
        capability_governance = dashboard.get("ai_runtime_capability_governance") or {}
        policy_compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        policy_linter = dashboard.get("ai_runtime_policy_linter") or {}
        command_layer = dashboard.get("ai_runtime_command_layer") or {}
        governance_court = dashboard.get("ai_runtime_governance_court_center") or {}

        high_risk = cls._high_risk_capabilities(capability_matrix, capability_governance)
        human_only = cls._human_only_capabilities(capability_matrix, capability_governance)
        forbidden = cls._forbidden_capabilities(capability_matrix, capability_governance, governance_court)
        delegation_risks = cls._delegation_risks(capability_governance)
        policy_summary = cls._policy_conflicts_summary(policy_compiler, policy_linter)
        command_summary = cls._command_layer_summary(command_layer)
        overview = cls._capability_governance_overview(
            capability_matrix,
            capability_governance,
            high_risk,
            human_only,
            forbidden,
            delegation_risks,
        )
        status = cls._summary_status(
            high_risk,
            human_only,
            forbidden,
            delegation_risks,
            policy_summary,
            command_summary,
            policy_linter,
            capability_governance,
        )

        return {
            "summary_status": status,
            "summary": cls._summary(status, overview, policy_summary, command_summary),
            "capability_governance_overview": overview,
            "high_risk_capabilities": high_risk[:10],
            "human_only_capabilities": human_only[:10],
            "forbidden_capabilities": forbidden[:10],
            "delegation_risks": delegation_risks[:10],
            "policy_conflicts_summary": policy_summary,
            "command_layer_summary": command_summary,
            "recommended_actions": cls._recommended_actions(status, high_risk, human_only, forbidden, delegation_risks, policy_summary, command_summary)[:10],
        }

    @classmethod
    def build_governance_summary_text(cls, summary: dict | None = None) -> str:
        summary = summary or {}
        lines = [
            "【AI Runtime 治理汇总中心】",
            f"状态：{summary.get('summary_status') or 'stable'}",
            f"摘要：{summary.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = summary.get(key) or []
            for item in items[:10]:
                lines.append(cls._format_item(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        lines.append("策略冲突摘要：")
        lines.append(cls._format_summary(summary.get("policy_conflicts_summary") or {}))
        lines.append("")
        lines.append("命令层摘要：")
        lines.append(cls._format_summary(summary.get("command_layer_summary") or {}))
        return "\n".join(lines).rstrip()

    @classmethod
    def build_governance_summary_markdown(cls, summary: dict | None = None) -> str:
        summary = summary or {}
        lines = [
            "# AI Runtime 治理汇总中心",
            "",
            f"- 状态：{summary.get('summary_status') or 'stable'}",
            f"- 摘要：{summary.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = summary.get(key) or []
            for item in items[:10]:
                lines.append(cls._format_item(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        lines.append("## 策略冲突摘要")
        lines.append(cls._format_summary(summary.get("policy_conflicts_summary") or {}))
        lines.append("")
        lines.append("## 命令层摘要")
        lines.append(cls._format_summary(summary.get("command_layer_summary") or {}))
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_governance_summary_rows(summary: dict | None = None) -> list[dict]:
        rows = []
        for category, key in [
            ("高风险能力", "high_risk_capabilities"),
            ("人工能力", "human_only_capabilities"),
            ("禁止能力", "forbidden_capabilities"),
            ("委托风险", "delegation_risks"),
            ("建议动作", "recommended_actions"),
        ]:
            for item in (summary or {}).get(key) or []:
                rows.append({
                    "类别": category,
                    "项目": AIRuntimeGovernanceSummaryService._item_title(item),
                    "风险": AIRuntimeGovernanceSummaryService._item_risk(item),
                    "状态": (summary or {}).get("summary_status") or "",
                    "建议": AIRuntimeGovernanceSummaryService._item_summary(item),
                })
        return rows

    @classmethod
    def _capability_governance_overview(cls, matrix: dict, governance: dict, high_risk: list[dict], human_only: list[dict], forbidden: list[dict], delegation_risks: list[dict]) -> dict:
        capabilities = matrix.get("capabilities") or governance.get("governed_capabilities") or []
        restricted = [
            item for item in capabilities
            if item.get("maturity") == "restricted"
        ]
        if not restricted:
            restricted = governance.get("restricted_capabilities") or []
        return {
            "total_capabilities": len(capabilities),
            "high_risk_count": len(high_risk),
            "human_only_count": len(human_only),
            "forbidden_count": len(forbidden),
            "restricted_count": len(restricted),
            "delegation_risk_count": len(delegation_risks),
        }

    @classmethod
    def _high_risk_capabilities(cls, matrix: dict, governance: dict) -> list[dict]:
        items = []
        for item in matrix.get("capabilities") or []:
            if item.get("risk_level") in {"high", "critical"} or item.get("maturity") == "experimental":
                items.append(cls._normalize_capability(item))
        for item in governance.get("governed_capabilities") or []:
            if item.get("risk_level") in {"high", "critical"} or item.get("maturity") == "experimental":
                items.append(cls._normalize_capability(item))
        if governance.get("governance_status") in {"attention", "critical", "warning"}:
            for item in governance.get("approval_required_capabilities") or []:
                items.append(cls._normalize_capability(item))
        return cls._dedupe(items)

    @classmethod
    def _human_only_capabilities(cls, matrix: dict, governance: dict) -> list[dict]:
        items = []
        for key in ["human_required_capabilities", "human_only_capabilities", "approval_required_capabilities"]:
            for item in matrix.get(key) or []:
                if item.get("human_required") or item.get("human_only") or item.get("HumanOnly"):
                    items.append(cls._normalize_capability(item))
            for item in governance.get(key) or []:
                if item.get("human_required") or item.get("human_only") or item.get("HumanOnly") or key == "human_only_capabilities":
                    items.append(cls._normalize_capability(item))
        for item in matrix.get("capabilities") or []:
            if item.get("human_required"):
                items.append(cls._normalize_capability(item))
        return cls._dedupe(items)

    @classmethod
    def _forbidden_capabilities(cls, matrix: dict, governance: dict, governance_court: dict) -> list[dict]:
        items = []
        for key in ["forbidden_capabilities", "restricted_capabilities"]:
            for item in matrix.get(key) or []:
                if item.get("forbidden") or item.get("maturity") == "restricted" or item.get("automation_allowed") is False:
                    items.append(cls._normalize_capability(item))
            for item in governance.get(key) or []:
                if item.get("forbidden") or item.get("maturity") == "restricted" or item.get("automation_allowed") is False:
                    items.append(cls._normalize_capability(item))
        for item in matrix.get("capabilities") or []:
            if item.get("automation_allowed") is False and item.get("maturity") == "restricted":
                items.append(cls._normalize_capability(item))
        for domain in governance_court.get("forbidden_domains") or []:
            items.append({
                "capability_key": f"GOVERNANCE_COURT_FORBIDDEN_{abs(hash(str(domain))) % 100000}",
                "title": cls._item_title(domain),
                "risk_level": cls._item_risk(domain) or "critical",
                "maturity": "restricted",
                "summary": cls._item_summary(domain) or "Governance Court forbidden domain.",
            })
        return cls._dedupe(items)

    @classmethod
    def _delegation_risks(cls, governance: dict) -> list[dict]:
        return [
            dict(item)
            for item in (governance.get("delegation_risks") or [])[:10]
        ]

    @classmethod
    def _policy_conflicts_summary(cls, compiler: dict, linter: dict) -> dict:
        conflicts = []
        conflicts.extend(compiler.get("policy_conflicts") or [])
        conflicts.extend(linter.get("critical_issues") or [])
        conflicts.extend(linter.get("warning_issues") or [])
        conflicts.extend(linter.get("conflicting_policies") or [])
        critical_count = sum(1 for item in conflicts if cls._item_risk(item) in {"critical", "high"} or item.get("severity") == "critical")
        warning_count = sum(1 for item in conflicts if cls._item_risk(item) == "warning" or item.get("severity") == "warning")
        return {
            "conflict_count": len(conflicts),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "top_conflicts": conflicts[:8],
        }

    @staticmethod
    def _command_layer_summary(command_layer: dict) -> dict:
        recommended = command_layer.get("recommended_commands") or []
        high_priority = command_layer.get("high_priority_commands") or []
        human_review = command_layer.get("human_review_commands") or []
        blocked = command_layer.get("blocked_commands") or []
        top_commands = (blocked + high_priority + human_review + recommended)[:8]
        return {
            "recommended_count": len(recommended),
            "high_priority_count": len(high_priority),
            "human_review_count": len(human_review),
            "blocked_count": len(blocked),
            "top_commands": top_commands,
        }

    @staticmethod
    def _summary_status(high_risk: list[dict], human_only: list[dict], forbidden: list[dict], delegation_risks: list[dict], policy_summary: dict, command_summary: dict, linter: dict, governance: dict) -> str:
        has_delegation_critical = any(item.get("risk_level") in {"critical", "high"} for item in delegation_risks)
        has_command_block = bool(command_summary.get("blocked_count") or command_summary.get("high_priority_count"))
        if forbidden or has_delegation_critical or policy_summary.get("critical_count") or has_command_block:
            return "critical"
        if high_risk or human_only or linter.get("linter_status") == "warning" or governance.get("governance_status") in {"warning", "attention"}:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(status: str, overview: dict, policy_summary: dict, command_summary: dict) -> str:
        if status == "critical":
            return f"治理汇总发现 forbidden/high-risk 治理风险，涉及 {overview.get('total_capabilities', 0)} 项能力、{policy_summary.get('critical_count', 0)} 个关键策略问题、{command_summary.get('blocked_count', 0)} 条阻断命令。"
        if status == "attention":
            return f"治理汇总需要关注 {overview.get('high_risk_count', 0)} 项高风险能力与 {overview.get('human_only_count', 0)} 项人工能力。"
        return f"治理汇总覆盖 {overview.get('total_capabilities', 0)} 项能力，当前无明显治理风险。"

    @staticmethod
    def _recommended_actions(status: str, high_risk: list[dict], human_only: list[dict], forbidden: list[dict], delegation_risks: list[dict], policy_summary: dict, command_summary: dict) -> list[str]:
        actions = []
        if high_risk:
            actions.append("优先复核 high risk capabilities。")
        if forbidden:
            actions.append("禁止开放 forbidden capabilities。")
        if human_only:
            actions.append("保持 HumanOnly 能力人工审批。")
        if delegation_risks:
            actions.append("复查 Capability Governance delegation risks。")
        if policy_summary.get("critical_count"):
            actions.append("复查 Policy Linter critical issues。")
        if command_summary.get("blocked_count"):
            actions.append("复查 Command Layer blocked commands。")
        actions.append("定期导出治理汇总报告。")
        if status == "stable":
            actions.insert(0, "保持治理汇总只读观察。")
        return actions[:10]

    @staticmethod
    def _normalize_capability(item: dict) -> dict:
        return {
            "capability_key": item.get("capability_key") or item.get("policy") or item.get("risk_key") or str(abs(hash(str(item))) % 100000),
            "title": AIRuntimeGovernanceSummaryService._item_title(item),
            "category": item.get("category") or "",
            "maturity": item.get("maturity") or "",
            "risk_level": AIRuntimeGovernanceSummaryService._item_risk(item),
            "human_required": bool(item.get("human_required") or item.get("human_only") or item.get("HumanOnly")),
            "summary": AIRuntimeGovernanceSummaryService._item_summary(item),
        }

    @staticmethod
    def _item_title(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("title") or item.get("capability") or item.get("policy") or item.get("issue") or item.get("risk_key") or item.get("command_key") or item)
        return str(item)

    @staticmethod
    def _item_risk(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("risk_level") or item.get("risk") or item.get("severity") or item.get("priority") or "")
        return ""

    @staticmethod
    def _item_summary(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("summary") or item.get("recommendation") or item.get("description") or item.get("reason") or item.get("title") or "")
        return str(item)

    @staticmethod
    def _format_item(item: object) -> str:
        return f"- {AIRuntimeGovernanceSummaryService._item_title(item)} / {AIRuntimeGovernanceSummaryService._item_risk(item)} / {AIRuntimeGovernanceSummaryService._item_summary(item)}"

    @staticmethod
    def _format_summary(summary: dict) -> str:
        pairs = [
            f"{key}={value}"
            for key, value in summary.items()
            if key != "top_conflicts" and key != "top_commands"
        ]
        return "- " + " / ".join(pairs) if pairs else "- 暂无"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("高风险能力", "high_risk_capabilities"),
            ("人工能力", "human_only_capabilities"),
            ("禁止能力", "forbidden_capabilities"),
            ("委托风险", "delegation_risks"),
            ("建议动作", "recommended_actions"),
        ]

    @staticmethod
    def _dedupe(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            key = item.get("capability_key") or item.get("title") or str(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
