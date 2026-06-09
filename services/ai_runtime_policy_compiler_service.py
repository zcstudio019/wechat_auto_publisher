"""Read-only Runtime OS policy compiler.

The compiler only aggregates governance signals into a policy matrix for
display and export. It never changes runtime state or triggers actions.
"""


class AIRuntimePolicyCompilerService:
    """Compile governance centers into a unified, read-only policy matrix."""

    @classmethod
    def build_policy_compiler(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        compiled_policies = cls._compiled_policies(dashboard)
        policy_conflicts = cls._policy_conflicts(dashboard)
        policy_matrix = cls._policy_matrix(compiled_policies)
        human_only_policies = [p for p in compiled_policies if p.get("human_required")]
        blocked_policies = [p for p in compiled_policies if p.get("status") == "blocked"]
        warning_policies = [p for p in compiled_policies if p.get("status") == "warning"]
        compiler_status = cls._compiler_status(blocked_policies, warning_policies, policy_conflicts)

        return {
            "compiler_status": compiler_status,
            "summary": cls._summary(compiler_status, compiled_policies, policy_conflicts),
            "compiled_policies": compiled_policies,
            "human_only_policies": human_only_policies,
            "blocked_policies": blocked_policies,
            "warning_policies": warning_policies,
            "policy_conflicts": policy_conflicts,
            "policy_matrix": policy_matrix,
            "recommended_actions": cls._recommended_actions(compiler_status),
        }

    @classmethod
    def build_policy_compiler_text(cls, compiler: dict | None = None) -> str:
        compiler = compiler or {}
        lines = [
            "【AI Runtime 策略编译器】",
            f"状态：{compiler.get('compiler_status') or 'normal'}",
            f"摘要：{compiler.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            for item in (compiler.get(key) or [])[:12]:
                lines.append(cls._format_line(item))
            if not (compiler.get(key) or []):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_policy_compiler_markdown(cls, compiler: dict | None = None) -> str:
        compiler = compiler or {}
        lines = [
            "# AI Runtime 策略编译器",
            "",
            f"- 状态：{compiler.get('compiler_status') or 'normal'}",
            f"- 摘要：{compiler.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            for item in (compiler.get(key) or [])[:12]:
                name = item.get("policy_key") or item.get("conflict_key") or "POLICY"
                source = item.get("source") or ""
                risk = item.get("risk_level") or ""
                status = item.get("status") or ""
                summary = item.get("summary") or ""
                lines.append(f"- `{name}` {source} / {risk} / {status}: {summary}")
            if not (compiler.get(key) or []):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_policy_compiler_rows(compiler: dict | None = None) -> list[dict]:
        rows = []
        for policy in (compiler or {}).get("compiled_policies") or []:
            rows.append({
                "Policy": policy.get("policy_key") or "",
                "Source": policy.get("source") or "",
                "Risk": policy.get("risk_level") or "",
                "HumanOnly": str(bool(policy.get("human_required"))),
                "Status": policy.get("status") or "",
                "Summary": policy.get("summary") or "",
            })
        return rows

    @classmethod
    def _compiled_policies(cls, dashboard: dict) -> list[dict]:
        policies = []
        policies.extend(cls._from_constitution(dashboard.get("ai_runtime_constitution_center") or {}))
        policies.extend(cls._from_boundary(dashboard.get("ai_runtime_boundary_center") or {}))
        policies.extend(cls._from_judgment(dashboard.get("ai_runtime_judgment_center") or {}))
        policies.extend(cls._from_governance_court(dashboard.get("ai_runtime_governance_court_center") or {}))
        policies.extend(cls._from_civilization(dashboard.get("ai_runtime_civilization_center") or {}))
        policies.extend(cls._from_integrity(dashboard.get("ai_runtime_integrity_center") or {}))
        policies.extend(cls._from_immune(dashboard.get("ai_runtime_immune_center") or {}))
        if not policies:
            policies.extend(cls._baseline_policies())
        return cls._dedupe(policies)

    @classmethod
    def _from_constitution(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Constitution",
            [
                ("principles", "constitution", "allowed", "low", False),
                ("constraints", "constitution", "restricted", "medium", True),
                ("constitution_constraints", "constitution", "restricted", "medium", True),
                ("constitutional_conflicts", "constitution_conflict", "warning", "high", True),
                ("violations", "constitution_violation", "blocked", "critical", True),
            ],
        )

    @classmethod
    def _from_boundary(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Boundary",
            [
                ("boundary_rules", "boundary", "restricted", "medium", True),
                ("boundary_constraints", "boundary", "restricted", "medium", True),
                ("forbidden_actions", "boundary_forbidden", "blocked", "critical", True),
                ("boundary_violations", "boundary_violation", "blocked", "critical", True),
            ],
        )

    @classmethod
    def _from_judgment(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Judgment",
            [
                ("acceptable_risks", "acceptable_risk", "allowed", "low", False),
                ("unacceptable_risks", "unacceptable_risk", "blocked", "critical", True),
                ("dangerous_automations", "dangerous_automation", "blocked", "critical", True),
                ("human_only_domains", "human_only", "restricted", "high", True),
                ("unsafe_high_confidence_items", "unsafe_confidence", "warning", "high", True),
                ("governance_violations", "governance_violation", "blocked", "critical", True),
                ("long_term_rejections", "long_term_rejection", "blocked", "high", True),
            ],
        )

    @classmethod
    def _from_governance_court(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Governance Court",
            [
                ("allowed_domains", "allowed_domain", "allowed", "low", False),
                ("restricted_domains", "restricted_domain", "restricted", "medium", True),
                ("forbidden_domains", "forbidden_domain", "blocked", "critical", True),
                ("human_sovereignty_domains", "human_sovereignty", "restricted", "critical", True),
                ("constitutional_conflicts", "constitutional_conflict", "warning", "critical", True),
                ("permanent_prohibitions", "permanent_prohibition", "blocked", "critical", True),
            ],
        )

    @classmethod
    def _from_civilization(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Civilization",
            [
                ("core_values", "core_value", "allowed", "low", False),
                ("human_first_principles", "human_first", "restricted", "high", True),
                ("forbidden_civilization_paths", "forbidden_path", "blocked", "critical", True),
                ("long_term_survival_principles", "survival_principle", "restricted", "medium", False),
                ("civilization_conflicts", "civilization_conflict", "warning", "high", True),
            ],
        )

    @classmethod
    def _from_integrity(cls, center: dict) -> list[dict]:
        policies = cls._from_center(
            center,
            "Integrity",
            [
                ("governance_conflicts", "governance_conflict", "warning", "high", True),
                ("civilization_conflicts", "civilization_conflict", "warning", "high", True),
                ("strategy_conflicts", "strategy_conflict", "warning", "high", True),
                ("automation_boundary_violations", "automation_boundary", "blocked", "critical", True),
                ("trust_integrity_risks", "trust_integrity", "warning", "high", True),
                ("cognitive_dissonance", "cognitive_dissonance", "warning", "high", True),
                ("value_fragmentations", "value_fragmentation", "warning", "high", True),
            ],
        )
        score = cls._safe_int(center.get("integrity_score"))
        if score is not None:
            risk = "critical" if score < 50 else "high" if score < 70 else "low"
            status = "warning" if score < 70 else "allowed"
            policies.append(cls._policy("POLICY_INTEGRITY_SCORE", "Integrity", "integrity_score", risk, score < 70, status, f"Integrity score: {score}"))
        return policies

    @classmethod
    def _from_immune(cls, center: dict) -> list[dict]:
        return cls._from_center(
            center,
            "Immune",
            [
                ("systemic_risks", "systemic_risk", "warning", "critical", True),
                ("governance_corruption_risks", "governance_corruption", "warning", "critical", True),
                ("civilization_regression_risks", "civilization_regression", "warning", "critical", True),
                ("integrity_collapse_risks", "integrity_collapse", "warning", "critical", True),
                ("dangerous_automation_patterns", "dangerous_automation", "blocked", "critical", True),
                ("trust_decay_patterns", "trust_decay", "warning", "high", True),
                ("high_risk_mutations", "high_risk_mutation", "warning", "critical", True),
                ("immune_alerts", "immune_alert", "warning", "critical", True),
            ],
        )

    @classmethod
    def _from_center(cls, center: dict, source: str, mappings: list[tuple[str, str, str, str, bool]]) -> list[dict]:
        policies = []
        for field, category, status, default_risk, human_required in mappings:
            for item in center.get(field) or []:
                summary = cls._summary_from_item(item)
                risk = cls._risk_from_item(item) or default_risk
                policies.append(cls._policy(
                    cls._policy_key(source, category, summary),
                    source,
                    category,
                    risk,
                    human_required or risk in {"high", "critical"} or status == "blocked",
                    status,
                    summary,
                ))
        status_value = cls._center_status(center)
        if status_value:
            policies.append(cls._policy(
                cls._policy_key(source, "status", status_value),
                source,
                "center_status",
                cls._risk_from_status(status_value),
                status_value in {"critical", "blocked", "warning", "attention"},
                cls._policy_status_from_status(status_value),
                f"{source} status: {status_value}",
            ))
        return policies

    @classmethod
    def _policy_matrix(cls, policies: list[dict]) -> list[dict]:
        rows = []
        for policy in policies:
            status = policy.get("status") or ""
            rows.append({
                "Layer": policy.get("category") or "",
                "Policy": policy.get("policy_key") or "",
                "Allowed": status == "allowed",
                "Restricted": status in {"restricted", "warning"},
                "Forbidden": status == "blocked",
                "HumanOnly": bool(policy.get("human_required")),
                "RiskLevel": policy.get("risk_level") or "",
                "Source": policy.get("source") or "",
            })
        return rows

    @classmethod
    def _policy_conflicts(cls, dashboard: dict) -> list[dict]:
        conflicts = []
        strategy = dashboard.get("ai_runtime_strategy_center") or {}
        boundary = dashboard.get("ai_runtime_boundary_center") or {}
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        command_layer = dashboard.get("ai_runtime_command_layer") or {}
        civilization = dashboard.get("ai_runtime_civilization_center") or {}
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        fitness = dashboard.get("ai_runtime_evolutionary_fitness_center") or {}

        if cls._has_any(strategy, ["automation_roadmap", "long_term_strategies"]):
            conflicts.append(cls._conflict("CONSTITUTION_VS_STRATEGY", "Constitution vs Strategy", "medium", "Strategy roadmap requires constitution alignment review."))
        if cls._has_any(boundary, ["boundary_violations", "forbidden_actions"]) or cls._has_any(judgment, ["dangerous_automations"]):
            conflicts.append(cls._conflict("BOUNDARY_VS_AUTOMATION", "Boundary vs Automation", "critical", "Automation expansion conflicts with explicit boundary constraints."))
        if cls._has_any(judgment, ["governance_violations", "unacceptable_risks"]) or cls._has_any(command_layer, ["blocked_commands", "human_review_commands"]):
            conflicts.append(cls._conflict("JUDGMENT_VS_COMMAND", "Judgment vs Command", "high", "Command recommendations require judgment-layer human review."))
        if cls._has_any(civilization, ["civilization_conflicts", "forbidden_civilization_paths"]) or cls._has_any(court, ["constitutional_conflicts", "forbidden_domains"]):
            conflicts.append(cls._conflict("CIVILIZATION_VS_GOVERNANCE", "Civilization vs Governance", "high", "Governance posture must stay aligned with civilization constraints."))
        if cls._has_any(integrity, ["strategy_conflicts", "cognitive_dissonance", "value_fragmentations"]) or cls._has_any(adaptive, ["strategic_obsolescence_risks", "required_adaptations"]):
            conflicts.append(cls._conflict("INTEGRITY_VS_ADAPTIVE", "Integrity vs Adaptive", "high", "Adaptive pressure may conflict with runtime integrity requirements."))
        if cls._has_any(immune, ["high_risk_mutations", "immune_alerts", "dangerous_automation_patterns"]) or cls._has_any(fitness, ["extinction_risks", "maladaptation_risks"]):
            conflicts.append(cls._conflict("IMMUNE_VS_EVOLUTIONARY_FITNESS", "Immune vs Evolutionary Fitness", "critical", "Evolutionary pressure requires immune-system and human review."))
        return conflicts

    @staticmethod
    def _policy(policy_key: str, source: str, category: str, risk_level: str, human_required: bool, status: str, summary: str) -> dict:
        return {
            "policy_key": policy_key,
            "source": source,
            "category": category,
            "risk_level": risk_level,
            "human_required": bool(human_required),
            "status": status,
            "summary": summary,
        }

    @staticmethod
    def _conflict(conflict_key: str, source: str, risk_level: str, summary: str) -> dict:
        return {
            "conflict_key": conflict_key,
            "source": source,
            "category": "policy_conflict",
            "risk_level": risk_level,
            "human_required": True,
            "status": "warning",
            "summary": summary,
        }

    @staticmethod
    def _baseline_policies() -> list[dict]:
        return [
            AIRuntimePolicyCompilerService._policy(
                "POLICY_READ_ONLY_RUNTIME_ANALYSIS",
                "Runtime Baseline",
                "read_only",
                "low",
                False,
                "allowed",
                "Runtime OS may compile, aggregate, display and export policy data.",
            ),
            AIRuntimePolicyCompilerService._policy(
                "POLICY_HUMAN_SOVEREIGNTY_REQUIRED",
                "Governance Baseline",
                "human_only",
                "critical",
                True,
                "blocked",
                "Publishing, approval, governance override and destructive operations require humans.",
            ),
            AIRuntimePolicyCompilerService._policy(
                "POLICY_NO_AUTOMATIC_POLICY_ACTION",
                "Runtime Baseline",
                "forbidden",
                "critical",
                True,
                "blocked",
                "The policy compiler must not automatically block, recover, approve, publish or mutate Runtime.",
            ),
        ]

    @staticmethod
    def _compiler_status(blocked: list[dict], warning: list[dict], conflicts: list[dict]) -> str:
        if blocked or any(conflict.get("risk_level") == "critical" for conflict in conflicts):
            return "critical"
        if warning or conflicts:
            return "warning"
        return "normal"

    @staticmethod
    def _summary(status: str, policies: list[dict], conflicts: list[dict]) -> str:
        if status == "critical":
            return f"策略编译器生成 {len(policies)} 条只读策略，发现阻断项或 critical 冲突，需要人工复核。"
        if status == "warning":
            return f"策略编译器生成 {len(policies)} 条只读策略，发现 {len(conflicts)} 条冲突提示。"
        return f"策略编译器生成 {len(policies)} 条只读策略，当前无明显策略冲突。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return [
                "人工复核 blocked_policies 与 policy_conflicts。",
                "保持策略编译器只读，不执行阻断、恢复或 Runtime 修改。",
            ]
        if status == "warning":
            return [
                "检查 warning_policies 与 policy_conflicts。",
                "必要时导出策略矩阵供人工治理复核。",
            ]
        return ["查看 policy_matrix，保持只读策略归档。"]

    @staticmethod
    def _format_line(item: dict) -> str:
        name = item.get("policy_key") or item.get("conflict_key") or "POLICY"
        source = item.get("source") or ""
        risk = item.get("risk_level") or ""
        status = item.get("status") or ""
        summary = item.get("summary") or ""
        return f"- {name} / {source} / {risk} / {status} / {summary}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("编译策略", "compiled_policies"),
            ("人工策略", "human_only_policies"),
            ("阻断策略", "blocked_policies"),
            ("警告策略", "warning_policies"),
            ("策略冲突", "policy_conflicts"),
        ]

    @staticmethod
    def _policy_key(source: str, category: str, summary: str) -> str:
        cleaned_source = "".join(ch if ch.isalnum() else "_" for ch in source.upper()).strip("_")
        cleaned_category = "".join(ch if ch.isalnum() else "_" for ch in category.upper()).strip("_")
        return f"POLICY_{cleaned_source}_{cleaned_category}_{abs(hash(summary)) % 100000}"

    @staticmethod
    def _summary_from_item(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("title") or item.get("name") or item.get("summary") or item.get("description") or item)
        return str(item)

    @staticmethod
    def _risk_from_item(item: object) -> str:
        if isinstance(item, dict):
            risk = item.get("risk_level") or item.get("risk") or item.get("severity")
            if risk in {"low", "medium", "high", "critical"}:
                return str(risk)
        return ""

    @staticmethod
    def _center_status(center: dict) -> str:
        for key in [
            "constitution_status",
            "boundary_status",
            "judgment_status",
            "court_status",
            "civilization_status",
            "integrity_status",
            "immune_status",
        ]:
            if center.get(key):
                return str(center.get(key))
        return ""

    @staticmethod
    def _risk_from_status(status: str) -> str:
        if status in {"critical", "blocked"}:
            return "critical"
        if status in {"warning", "attention", "fragile"}:
            return "high"
        return "low"

    @staticmethod
    def _policy_status_from_status(status: str) -> str:
        if status in {"critical", "blocked"}:
            return "blocked"
        if status in {"warning", "attention", "fragile"}:
            return "warning"
        return "allowed"

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _has_any(center: dict, keys: list[str]) -> bool:
        return any(bool(center.get(key)) for key in keys)

    @staticmethod
    def _dedupe(policies: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for policy in policies:
            key = (policy.get("source"), policy.get("category"), policy.get("summary"))
            if key in seen:
                continue
            seen.add(key)
            result.append(policy)
        return result
