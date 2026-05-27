"""Read-only governance court analysis for AI Runtime OS."""


class AIRuntimeGovernanceCourtEngine:
    """Build final governance rulings without executing or enforcing them."""

    def build_governance_court(
        self,
        judgment_center,
        constitution_center,
        boundary_center,
        policy_gate_center,
        trust_center,
        delegation_center,
    ) -> dict:
        judgment_center = judgment_center or {}
        constitution_center = constitution_center or {}
        boundary_center = boundary_center or {}
        policy_gate_center = policy_gate_center or {}
        trust_center = trust_center or {}
        delegation_center = delegation_center or {}

        allowed_domains = self._allowed_domains()
        restricted_domains = self._restricted_domains(judgment_center, trust_center)
        forbidden_domains = self._forbidden_domains(judgment_center)
        human_sovereignty_domains = self._human_sovereignty_domains()
        constitutional_conflicts = self._constitutional_conflicts(
            judgment_center,
            constitution_center,
            boundary_center,
            policy_gate_center,
        )
        governance_overrides = self._governance_overrides(
            judgment_center,
            constitution_center,
            boundary_center,
            trust_center,
            delegation_center,
        )
        court_rulings = self._court_rulings(
            judgment_center,
            forbidden_domains,
            constitutional_conflicts,
            governance_overrides,
            delegation_center,
        )
        permanent_prohibitions = self._permanent_prohibitions()
        status = self._status(forbidden_domains, constitutional_conflicts, court_rulings)

        return {
            "court_status": status,
            "allowed_domains": allowed_domains,
            "restricted_domains": restricted_domains,
            "forbidden_domains": forbidden_domains,
            "human_sovereignty_domains": human_sovereignty_domains,
            "court_rulings": court_rulings,
            "constitutional_conflicts": constitutional_conflicts,
            "governance_overrides": governance_overrides,
            "permanent_prohibitions": permanent_prohibitions,
            "court_summary": self._summary(
                allowed_domains,
                restricted_domains,
                forbidden_domains,
                court_rulings,
                constitutional_conflicts,
            ),
            "recommended_actions": self._recommended_actions(status),
        }

    def _allowed_domains(self) -> list[dict]:
        return [
            self._domain("reporting", "allowed_domain", "allow", "low", "Reporting is allowed when it remains read-only.", "Keep reporting non-mutating."),
            self._domain("export", "allowed_domain", "allow", "low", "Export is allowed when it only serializes existing analysis.", "Keep exports read-only."),
            self._domain("dashboard analysis", "allowed_domain", "allow", "low", "Dashboard analysis can aggregate state without writing business data.", "Use dashboards for observation only."),
            self._domain("simulation analysis", "allowed_domain", "allow", "medium", "Simulation analysis is allowed as scenario planning only.", "Label simulation as advisory, not executable."),
        ]

    def _restricted_domains(self, judgment: dict, trust: dict) -> list[dict]:
        domains = [
            self._domain(
                "intervention recommendation",
                "restricted_domain",
                "restricted",
                "medium",
                "Intervention planning may guide humans but cannot trigger intervention.",
                "Require manual approval before any operational change.",
            ),
            self._domain(
                "release preparation",
                "restricted_domain",
                "restricted",
                "high",
                "Release preparation is analysis-only unless human authorization exists.",
                "Keep release authorization human-only.",
            ),
            self._domain(
                "governance recommendation",
                "restricted_domain",
                "restricted",
                "high",
                "Governance recommendations can inform review but cannot rewrite governance.",
                "Route governance changes to manual review.",
            ),
        ]
        if self._level(trust, "trust") == "low" or judgment.get("judgment_status") == "critical":
            domains.append(self._domain(
                "delegation expansion",
                "restricted_domain",
                "restricted",
                "critical",
                "Delegation expansion is restricted under low trust or critical judgment.",
                "Pause delegation expansion until governance review is complete.",
            ))
        return domains

    def _forbidden_domains(self, judgment: dict) -> list[dict]:
        domains = [
            self._domain(
                "autonomous approval",
                "forbidden_domain",
                "forbidden",
                "critical",
                "Approval authority must not be automated.",
                "Reject autonomous approval permanently.",
            ),
            self._domain(
                "autonomous publish",
                "forbidden_domain",
                "forbidden",
                "critical",
                "Publishing changes external state and requires human authorization.",
                "Keep publishing human-only.",
            ),
            self._domain(
                "autonomous governance rewrite",
                "forbidden_domain",
                "forbidden",
                "critical",
                "Runtime must not rewrite its own governance constraints.",
                "Reject autonomous governance rewrite.",
            ),
            self._domain(
                "autonomous constitution modification",
                "forbidden_domain",
                "forbidden",
                "critical",
                "Constitution modification changes the highest safety rule set.",
                "Keep constitution modification human-only.",
            ),
            self._domain(
                "autonomous runtime repair",
                "forbidden_domain",
                "forbidden",
                "high",
                "Runtime repair can mutate state and obscure root causes.",
                "Generate repair plans only; never repair automatically.",
            ),
        ]
        if self._has_text(judgment.get("dangerous_automations"), ["override", "approval", "publishing", "repair"]):
            domains.append(self._domain(
                "dangerous automation path",
                "forbidden_domain",
                "forbidden",
                "critical",
                "Judgment layer detected a dangerous automation direction.",
                "Treat the path as forbidden by Governance Court.",
            ))
        return domains

    def _human_sovereignty_domains(self) -> list[dict]:
        return [
            self._domain("release authorization", "human_sovereignty_domain", "human_only", "critical", "Release authorization belongs to humans.", "Require explicit human authorization."),
            self._domain("governance override", "human_sovereignty_domain", "human_only", "critical", "Governance override changes the Runtime rule of law.", "Keep override authority human-only."),
            self._domain("destructive operation", "human_sovereignty_domain", "human_only", "critical", "Destructive operations require accountable human choice.", "Never automate destructive operations."),
            self._domain("production escalation", "human_sovereignty_domain", "human_only", "critical", "Production escalation requires human accountability.", "Escalate to humans only."),
            self._domain("permanent deletion", "human_sovereignty_domain", "human_only", "critical", "Permanent deletion cannot be delegated to Runtime autonomy.", "Keep deletion human-only and auditable."),
        ]

    def _court_rulings(
        self,
        judgment: dict,
        forbidden: list[dict],
        conflicts: list[dict],
        overrides: list[dict],
        delegation: dict,
    ) -> list[dict]:
        rulings = []
        if forbidden or self._has_text(judgment.get("dangerous_automations"), ["automation"]):
            rulings.append(self._domain(
                "automation expansion denied",
                "court_ruling",
                "denied",
                "critical",
                "Automation expansion is denied where it crosses forbidden or dangerous domains.",
                "Keep automation advisory and read-only.",
            ))
        if self._has_text(judgment.get("governance_violations"), ["governance", "policy", "boundary"]):
            rulings.append(self._domain(
                "governance override rejected",
                "court_ruling",
                "rejected",
                "critical",
                "Governance override attempts are rejected by the court layer.",
                "Route governance issues to manual review.",
            ))
        if conflicts:
            rulings.append(self._domain(
                "runtime autonomy restricted",
                "court_ruling",
                "restricted",
                "critical",
                "Constitutional or boundary conflicts restrict Runtime autonomy.",
                "Keep Runtime autonomy below human and constitutional authority.",
            ))
        if self._delegation_risky(delegation) or overrides:
            rulings.append(self._domain(
                "delegation paused",
                "court_ruling",
                "paused",
                "high",
                "Delegation is paused when trust, boundary, or human sovereignty is uncertain.",
                "Resume delegation only after manual governance review.",
            ))
        return rulings

    def _constitutional_conflicts(self, judgment: dict, constitution: dict, boundary: dict, policy_gate: dict) -> list[dict]:
        conflicts = []
        if self._has_text(judgment.get("unsafe_high_confidence_items"), ["strategy", "automation"]):
            conflicts.append(self._domain(
                "strategy conflicts with constitution",
                "constitutional_conflict",
                "conflict",
                "critical",
                "High-confidence strategy cannot override constitutional safety.",
                "Let constitution override strategic ambition.",
            ))
        if self._has_text(judgment.get("dangerous_automations"), ["automation"]) or self._unsafe_status(boundary, "boundary"):
            conflicts.append(self._domain(
                "automation conflicts with boundary",
                "constitutional_conflict",
                "conflict",
                "critical",
                "Automation expansion conflicts with Runtime boundary constraints.",
                "Let boundary override automation.",
            ))
        if self._unsafe_status(policy_gate, "policy_gate") or self._unsafe_status(constitution, "constitution"):
            conflicts.append(self._domain(
                "simulation conflicts with governance",
                "constitutional_conflict",
                "conflict",
                "high",
                "Simulation or confidence cannot proceed past unsafe governance gates.",
                "Treat governance safety as the upper rule.",
            ))
        return conflicts

    def _governance_overrides(self, judgment: dict, constitution: dict, boundary: dict, trust: dict, delegation: dict) -> list[dict]:
        overrides = [
            self._domain(
                "constitution overrides strategy",
                "governance_override",
                "override",
                "critical",
                "Constitutional constraints supersede strategic plans.",
                "Apply constitutional checks before strategy adoption.",
            ),
            self._domain(
                "boundary overrides automation",
                "governance_override",
                "override",
                "critical",
                "Boundary constraints supersede automation goals.",
                "Block automation that crosses boundary constraints.",
            ),
            self._domain(
                "trust overrides confidence",
                "governance_override",
                "override",
                "high",
                "Low trust must override high confidence.",
                "Do not allow confidence to bypass trust.",
            ),
            self._domain(
                "human sovereignty overrides delegation",
                "governance_override",
                "override",
                "critical",
                "Human sovereignty is the final authority over delegation.",
                "Keep delegation revocable and human-controlled.",
            ),
        ]
        if judgment.get("judgment_status") == "critical" or self._unsafe_status(constitution, "constitution"):
            overrides.append(self._domain(
                "court overrides runtime judgment",
                "governance_override",
                "override",
                "critical",
                "The court layer constrains Runtime judgment when judgment risk is critical.",
                "Use court rulings as final advisory safety boundaries.",
            ))
        if self._unsafe_status(boundary, "boundary") or self._level(trust, "trust") == "low" or self._delegation_risky(delegation):
            overrides.append(self._domain(
                "safety overrides delegation",
                "governance_override",
                "override",
                "critical",
                "Safety constraints override delegation under low trust or weak boundary.",
                "Pause delegation expansion.",
            ))
        return overrides

    def _permanent_prohibitions(self) -> list[dict]:
        return [
            self._domain("self modifying runtime", "permanent_prohibition", "prohibited", "critical", "Self-modifying Runtime can erase auditability and safety constraints.", "Reject uncontrolled self-modification permanently."),
            self._domain("autonomous governance rewrite", "permanent_prohibition", "prohibited", "critical", "Autonomous governance rewrite breaks Runtime rule of law.", "Keep governance rewrite human-only."),
            self._domain("autonomous approval authority", "permanent_prohibition", "prohibited", "critical", "Approval authority must remain accountable to humans.", "Reject autonomous approval authority."),
            self._domain("autonomous production release", "permanent_prohibition", "prohibited", "critical", "Production release changes operational reality.", "Keep production release human-authorized."),
        ]

    @staticmethod
    def _domain(title: str, domain_type: str, ruling: str, risk: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": domain_type,
            "ruling": ruling,
            "risk": risk,
            "summary": summary,
            "recommendation": recommendation,
        }

    @staticmethod
    def _has_text(items, needles: list[str]) -> bool:
        text = " ".join(str(item) for item in items or []).lower()
        return any(needle.lower() in text for needle in needles)

    @staticmethod
    def _level(center: dict, prefix: str) -> str:
        candidates = [
            center.get(f"{prefix}_level"),
            center.get(f"{prefix}_status"),
            center.get("level"),
            center.get("status"),
            center.get("score_label"),
        ]
        for value in candidates:
            normalized = str(value or "").lower()
            if normalized in {"low", "medium", "high"}:
                return normalized
            if normalized in {"critical", "blocked", "unsafe", "risky", "violation", "denied"}:
                return "low"
            if normalized in {"warning", "attention", "restricted"}:
                return "medium"
            if normalized in {"healthy", "stable", "safe", "pass", "passed", "allowed"}:
                return "high"
        score = center.get(f"{prefix}_score") or center.get("score")
        if isinstance(score, (int, float)):
            if score >= 75:
                return "high"
            if score >= 45:
                return "medium"
            return "low"
        return "medium"

    def _unsafe_status(self, center: dict, prefix: str) -> bool:
        return self._level(center, prefix) == "low" or str(center.get("gate_status") or "").lower() in {
            "blocked",
            "unsafe",
            "violation",
            "denied",
        }

    @staticmethod
    def _delegation_risky(delegation: dict) -> bool:
        status_text = " ".join(str(value) for value in delegation.values()).lower()
        return any(token in status_text for token in ["blocked", "critical", "unsafe", "pause", "paused", "denied"])

    @staticmethod
    def _status(forbidden: list[dict], conflicts: list[dict], rulings: list[dict]) -> str:
        severe_conflicts = any(item.get("risk") == "critical" for item in conflicts)
        forbidden_violated = bool(forbidden)
        critical_rulings = sum(1 for item in rulings if item.get("risk") == "critical")
        if forbidden_violated or severe_conflicts or critical_rulings >= 2:
            return "critical"
        if conflicts or rulings:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(
        allowed: list[dict],
        restricted: list[dict],
        forbidden: list[dict],
        rulings: list[dict],
        conflicts: list[dict],
    ) -> str:
        return (
            f"Court classified {len(allowed)} allowed domain(s), "
            f"{len(restricted)} restricted domain(s), "
            f"{len(forbidden)} forbidden domain(s), "
            f"{len(rulings)} court ruling(s), and "
            f"{len(conflicts)} constitutional conflict(s)."
        )

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        actions = [
            "Keep Governance Court read-only; do not automatically execute rulings or modify governance.",
            "Treat court rulings as final advisory boundaries for human review.",
        ]
        if status == "critical":
            actions.append("Preserve human sovereignty and reject forbidden automation before any operational expansion.")
        elif status == "attention":
            actions.append("Review restricted domains and court rulings before relying on Runtime recommendations.")
        return actions
