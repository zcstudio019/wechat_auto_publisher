"""Read-only Runtime OS capability matrix service."""


class AIRuntimeCapabilityMatrixService:
    """Build a capability map from existing Runtime OS centers."""

    CATEGORIES = [
        "Runtime Analysis",
        "Governance",
        "Risk Detection",
        "Simulation",
        "Decision Support",
        "Export & Reporting",
        "Navigation",
        "Documentation",
        "Release Management",
        "Human Review",
        "Strategy",
        "Resilience",
        "Meta-Cognition",
    ]

    @classmethod
    def build_capability_matrix(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        capabilities = cls._capabilities(dashboard)
        readonly = [item for item in capabilities if item.get("readonly")]
        human_required = [item for item in capabilities if item.get("human_required")]
        forbidden = [item for item in capabilities if not item.get("automation_allowed") and item.get("maturity") == "restricted"]
        unstable = [item for item in capabilities if item.get("maturity") == "experimental" or item.get("risk_level") in {"high", "critical"}]
        high_maturity = [item for item in capabilities if item.get("maturity") in {"stable", "advanced"}]
        gaps = cls._capability_gaps(capabilities, dashboard)
        status = cls._status(forbidden, unstable, gaps)

        return {
            "matrix_status": status,
            "summary": cls._summary(status, capabilities, gaps),
            "capabilities": capabilities,
            "readonly_capabilities": readonly,
            "human_required_capabilities": human_required,
            "forbidden_capabilities": forbidden,
            "unstable_capabilities": unstable,
            "high_maturity_capabilities": high_maturity,
            "capability_gaps": gaps,
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_capability_matrix_text(cls, matrix: dict | None = None) -> str:
        matrix = matrix or {}
        lines = [
            "【AI Runtime OS 能力矩阵】",
            f"状态：{matrix.get('matrix_status') or 'stable'}",
            f"摘要：{matrix.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = matrix.get(key) or []
            for item in items[:12]:
                lines.append(cls._format_capability(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_capability_matrix_markdown(cls, matrix: dict | None = None) -> str:
        matrix = matrix or {}
        lines = [
            "# AI Runtime OS 能力矩阵",
            "",
            f"- 状态：{matrix.get('matrix_status') or 'stable'}",
            f"- 摘要：{matrix.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = matrix.get(key) or []
            for item in items[:12]:
                lines.append(cls._format_capability(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_capability_matrix_rows(matrix: dict | None = None) -> list[dict]:
        rows = []
        for item in (matrix or {}).get("capabilities") or []:
            rows.append({
                "Capability": item.get("title") or "",
                "Category": item.get("category") or "",
                "Maturity": item.get("maturity") or "",
                "Risk": item.get("risk_level") or "",
                "HumanRequired": str(bool(item.get("human_required"))),
                "Readonly": str(bool(item.get("readonly"))),
                "Summary": item.get("summary") or "",
            })
        return rows

    @classmethod
    def _capabilities(cls, dashboard: dict) -> list[dict]:
        items = []
        items.extend(cls._from_command_layer(dashboard.get("ai_runtime_command_layer") or {}))
        items.extend(cls._from_policy_compiler(dashboard.get("ai_runtime_policy_compiler") or {}))
        items.extend(cls._from_policy_linter(dashboard.get("ai_runtime_policy_linter") or {}))
        items.extend(cls._from_practical_console(dashboard.get("ai_runtime_practical_console") or {}))
        items.extend(cls._from_mission_control(dashboard.get("ai_runtime_mission_control_center") or dashboard.get("ai_runtime_task_command_center") or {}))
        items.extend(cls._from_center("Decision", "Decision Support", dashboard.get("ai_runtime_decision_center") or {}, ["recommended_decisions", "manual_only_decisions", "high_risk_decisions"]))
        items.extend(cls._from_center("Simulation", "Simulation", dashboard.get("ai_runtime_simulation_center") or {}, ["simulations", "risk_propagation_forecasts", "rollback_impacts"]))
        items.extend(cls._from_center("Strategy", "Strategy", dashboard.get("ai_runtime_strategy_center") or {}, ["short_term_strategies", "mid_term_strategies", "long_term_strategies", "stability_roadmap"]))
        items.extend(cls._from_center("Governance Court", "Governance", dashboard.get("ai_runtime_governance_court_center") or {}, ["allowed_domains", "restricted_domains", "forbidden_domains", "human_sovereignty_domains"]))
        items.extend(cls._from_center("Civilization", "Governance", dashboard.get("ai_runtime_civilization_center") or {}, ["core_values", "human_first_principles", "forbidden_civilization_paths"]))
        items.extend(cls._from_center("Integrity", "Risk Detection", dashboard.get("ai_runtime_integrity_center") or {}, ["consistency_checks", "governance_conflicts", "automation_boundary_violations", "trust_integrity_risks"]))
        items.extend(cls._from_center("Immune", "Risk Detection", dashboard.get("ai_runtime_immune_center") or {}, ["systemic_risks", "immune_alerts", "dangerous_automation_patterns", "trust_decay_patterns"]))
        items.extend(cls._from_center("Adaptive", "Strategy", dashboard.get("ai_runtime_adaptive_center") or {}, ["required_adaptations", "evolutionary_pressures", "long_term_survival_risks"]))
        items.extend(cls._from_center("Resilience", "Resilience", dashboard.get("ai_runtime_resilience_center") or {}, ["recovery_capabilities", "resilience_patterns", "antifragile_patterns", "collapse_risks"]))
        items.extend(cls._from_center("Evolutionary Fitness", "Resilience", dashboard.get("ai_runtime_evolutionary_fitness_center") or {}, ["high_fitness_structures", "low_fitness_structures", "extinction_risks", "selection_pressures"]))
        items.extend(cls._baseline_capabilities())
        return cls._dedupe(items)

    @classmethod
    def _from_command_layer(cls, command_layer: dict) -> list[dict]:
        items = []
        for key in ["recommended_commands", "human_review_commands", "blocked_commands"]:
            for command in command_layer.get(key) or []:
                risk = command.get("risk_level") or "medium"
                human = bool(command.get("human_required"))
                items.append(cls._capability(
                    command.get("command_key") or cls._key("COMMAND", command.get("title")),
                    command.get("title") or "Runtime command",
                    cls._category_from_text(command.get("category") or command.get("title")),
                    risk,
                    human,
                    True,
                    not human and risk not in {"high", "critical"},
                    command.get("description") or command.get("recommended_route") or "",
                    source_status=command_layer.get("command_layer_status"),
                    policy_supported=True,
                ))
        return items

    @classmethod
    def _from_policy_compiler(cls, compiler: dict) -> list[dict]:
        items = []
        for policy in compiler.get("compiled_policies") or []:
            risk = policy.get("risk_level") or "medium"
            status = policy.get("status") or ""
            human = bool(policy.get("human_required"))
            items.append(cls._capability(
                policy.get("policy_key") or cls._key("POLICY", policy.get("summary")),
                policy.get("summary") or policy.get("policy_key") or "Compiled policy",
                "Governance",
                risk,
                human,
                True,
                status not in {"blocked", "human_only"} and not human,
                f"{policy.get('source') or 'Policy'} / {status}",
                source_status=status,
                policy_supported=True,
            ))
        return items

    @classmethod
    def _from_policy_linter(cls, linter: dict) -> list[dict]:
        items = []
        for issue in linter.get("lint_issues") or []:
            severity = issue.get("severity") or "warning"
            items.append(cls._capability(
                cls._key("LINTER", issue.get("policy") or issue.get("issue")),
                issue.get("issue") or "Policy lint issue",
                "Risk Detection",
                "critical" if severity == "critical" else "high",
                True,
                True,
                False,
                issue.get("recommendation") or "",
                source_status=linter.get("linter_status"),
                policy_supported=True,
            ))
        return items

    @classmethod
    def _from_practical_console(cls, console: dict) -> list[dict]:
        items = []
        for key, category in [
            ("must_handle_today", "Human Review"),
            ("observe_today", "Runtime Analysis"),
            ("never_automate", "Governance"),
            ("weekly_improvement_focus", "Strategy"),
        ]:
            for entry in console.get(key) or []:
                risk = entry.get("priority") if isinstance(entry, dict) else "medium"
                title = cls._title(entry)
                items.append(cls._capability(
                    cls._key("PRACTICAL", title),
                    title,
                    category,
                    cls._risk_from_value(risk),
                    key in {"must_handle_today", "never_automate"},
                    True,
                    key not in {"must_handle_today", "never_automate"},
                    cls._summary_from_item(entry),
                    source_status=console.get("console_status"),
                    policy_supported=key == "never_automate",
                ))
        return items

    @classmethod
    def _from_mission_control(cls, mission: dict) -> list[dict]:
        return cls._from_center(
            "Mission Control",
            "Decision Support",
            mission,
            ["today_tasks", "blocked_tasks", "recommended_sequence", "manual_review_items"],
        )

    @classmethod
    def _from_center(cls, source: str, category: str, center: dict, fields: list[str]) -> list[dict]:
        items = []
        status = cls._first_status(center)
        for field in fields:
            for entry in center.get(field) or []:
                title = cls._title(entry)
                risk = cls._risk_from_item(entry, status)
                human = cls._human_required(entry, field, risk)
                automation_allowed = not human and risk not in {"high", "critical"} and "forbidden" not in field and "blocked" not in field
                items.append(cls._capability(
                    cls._key(source, f"{field}:{title}"),
                    title,
                    category,
                    risk,
                    human,
                    True,
                    automation_allowed,
                    cls._summary_from_item(entry),
                    source_status=status,
                    policy_supported=source in {"Governance Court", "Civilization", "Integrity", "Immune"},
                ))
        if status and not items:
            risk = cls._risk_from_value(status)
            items.append(cls._capability(
                cls._key(source, status),
                f"{source} status capability",
                category,
                risk,
                risk in {"high", "critical"},
                True,
                risk not in {"high", "critical"},
                f"{source} status: {status}",
                source_status=status,
                policy_supported=source in {"Governance Court", "Civilization", "Integrity", "Immune"},
            ))
        return items

    @classmethod
    def _capability(
        cls,
        capability_key: str,
        title: str,
        category: str,
        risk_level: str,
        human_required: bool,
        readonly: bool,
        automation_allowed: bool,
        summary: str,
        source_status: str | None = None,
        policy_supported: bool = False,
    ) -> dict:
        return {
            "capability_key": capability_key,
            "title": title,
            "category": category if category in cls.CATEGORIES else "Runtime Analysis",
            "maturity": cls._maturity(risk_level, human_required, automation_allowed, source_status, policy_supported),
            "risk_level": risk_level or "medium",
            "human_required": bool(human_required),
            "readonly": bool(readonly),
            "automation_allowed": bool(automation_allowed),
            "summary": summary or title,
        }

    @classmethod
    def _maturity(cls, risk: str, human_required: bool, automation_allowed: bool, status: str | None, policy_supported: bool) -> str:
        if not automation_allowed or human_required or status in {"blocked"}:
            return "restricted"
        if risk in {"high", "critical"} or status in {"warning", "critical", "attention", "urgent", "fragile", "unstable evolution"}:
            return "experimental"
        if policy_supported and status in {"stable", "clean", "healthy", "normal", "ready", "allowed", None, ""}:
            return "advanced"
        if status in {"stable", "clean", "healthy", "normal", "ready", "allowed"}:
            return "stable"
        return "basic"

    @staticmethod
    def _baseline_capabilities() -> list[dict]:
        return [
            AIRuntimeCapabilityMatrixService._capability("CAP_RUNTIME_ANALYSIS", "Runtime read-only analysis", "Runtime Analysis", "low", False, True, True, "Read-only runtime aggregation and inspection.", "stable", True),
            AIRuntimeCapabilityMatrixService._capability("CAP_EXPORT_REPORTING", "Runtime export and reporting", "Export & Reporting", "low", False, True, True, "Export Runtime reports without business mutation.", "stable", True),
            AIRuntimeCapabilityMatrixService._capability("CAP_NAVIGATION", "Runtime navigation", "Navigation", "low", False, True, True, "Route users to existing Dashboard pages.", "stable", False),
            AIRuntimeCapabilityMatrixService._capability("CAP_DOCUMENTATION", "Runtime documentation", "Documentation", "low", False, True, True, "Document and search Runtime modules.", "stable", False),
            AIRuntimeCapabilityMatrixService._capability("CAP_RELEASE_HUMAN_REVIEW", "Release human review", "Release Management", "critical", True, True, False, "Release authorization remains human-only.", "blocked", True),
            AIRuntimeCapabilityMatrixService._capability("CAP_META_COGNITION", "Runtime meta-cognition", "Meta-Cognition", "medium", False, True, True, "Identify blind spots and cognitive conflicts.", "stable", True),
        ]

    @classmethod
    def _capability_gaps(cls, capabilities: list[dict], dashboard: dict) -> list[dict]:
        existing = {item.get("category") for item in capabilities}
        gaps = [
            {"gap_key": cls._key("GAP", category), "title": f"{category} capability coverage missing", "category": category, "summary": "补充只读能力描述或确认该能力中心是否接入。"}
            for category in cls.CATEGORIES
            if category not in existing
        ]
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        if linter.get("linter_status") in {"warning", "critical"}:
            gaps.append({"gap_key": "GAP_POLICY_QUALITY", "title": "Policy quality gap", "category": "Governance", "summary": "Policy Linter 存在 warning/critical，需要人工复核能力边界。"})
        return gaps

    @staticmethod
    def _status(forbidden: list[dict], unstable: list[dict], gaps: list[dict]) -> str:
        if any(item.get("risk_level") == "critical" for item in forbidden):
            return "critical"
        if unstable or gaps:
            return "warning"
        return "stable"

    @staticmethod
    def _summary(status: str, capabilities: list[dict], gaps: list[dict]) -> str:
        if status == "critical":
            return f"能力矩阵聚合 {len(capabilities)} 项能力，存在 critical restricted 能力，需要人工复核。"
        if status == "warning":
            return f"能力矩阵聚合 {len(capabilities)} 项能力，发现 {len(gaps)} 项能力缺口或不稳定能力。"
        return f"能力矩阵聚合 {len(capabilities)} 项能力，当前能力地图稳定。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["人工复核 forbidden_capabilities 与 capability_gaps。", "保持能力矩阵只读，不开放自动执行。"]
        if status == "warning":
            return ["检查 unstable_capabilities 与 capability_gaps。", "按需导出能力矩阵供人工治理评审。"]
        return ["保留当前能力地图，按需用于导航和人工评审。"]

    @staticmethod
    def _format_capability(item: dict) -> str:
        return (
            f"- {item.get('title') or item.get('capability_key') or item.get('gap_key')} / "
            f"{item.get('category') or ''} / {item.get('maturity') or ''} / "
            f"{item.get('risk_level') or ''} / {item.get('summary') or ''}"
        )

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("高成熟能力", "high_maturity_capabilities"),
            ("不稳定能力", "unstable_capabilities"),
            ("禁止能力", "forbidden_capabilities"),
            ("能力缺口", "capability_gaps"),
        ]

    @staticmethod
    def _title(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("title") or item.get("name") or item.get("summary") or item.get("description") or item)
        return str(item)

    @staticmethod
    def _summary_from_item(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("summary") or item.get("description") or item.get("reason") or item.get("title") or item)
        return str(item)

    @staticmethod
    def _risk_from_item(item: object, status: str | None = None) -> str:
        if isinstance(item, dict):
            risk = item.get("risk_level") or item.get("risk") or item.get("severity") or item.get("priority")
            if risk:
                return AIRuntimeCapabilityMatrixService._risk_from_value(str(risk))
        return AIRuntimeCapabilityMatrixService._risk_from_value(status or "")

    @staticmethod
    def _risk_from_value(value: str) -> str:
        value = str(value or "").lower()
        if value in {"critical", "urgent", "blocked", "high"}:
            return "critical" if value in {"critical", "urgent", "blocked"} else "high"
        if value in {"warning", "attention", "medium", "conditional", "fragile", "risky", "unstable evolution"}:
            return "high"
        if value in {"low", "normal", "stable", "clean", "healthy", "ready", "safe", "allowed"}:
            return "low"
        return "medium"

    @staticmethod
    def _human_required(item: object, field: str, risk: str) -> bool:
        if isinstance(item, dict) and "human_required" in item:
            return bool(item.get("human_required"))
        return risk in {"high", "critical"} or any(token in field for token in ["blocked", "forbidden", "human", "manual", "risk"])

    @staticmethod
    def _first_status(center: dict) -> str:
        for key, value in center.items():
            if key.endswith("_status") and isinstance(value, str):
                return value
        return ""

    @staticmethod
    def _category_from_text(text: object) -> str:
        text = str(text or "").lower()
        if "export" in text or "report" in text:
            return "Export & Reporting"
        if "release" in text:
            return "Release Management"
        if "governance" in text or "policy" in text:
            return "Governance"
        if "review" in text or "human" in text:
            return "Human Review"
        if "navigation" in text or "search" in text or "open" in text:
            return "Navigation"
        if "documentation" in text or "runbook" in text:
            return "Documentation"
        return "Runtime Analysis"

    @staticmethod
    def _key(prefix: str, value: object) -> str:
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value or "item").upper()).strip("_")
        return f"CAP_{prefix.upper().replace(' ', '_')}_{cleaned[:48]}_{abs(hash(str(value))) % 100000}"

    @staticmethod
    def _dedupe(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            key = item.get("capability_key")
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
