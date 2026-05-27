"""Read-only judgment analysis for AI Runtime OS."""


class AIRuntimeJudgmentEngine:
    """Classify Runtime risks and automation boundaries without executing decisions."""

    def build_judgment(
        self,
        metacognition_center,
        strategy_center,
        trust_center,
        confidence_center,
        constitution_center,
        boundary_center,
        policy_gate_center,
    ) -> dict:
        metacognition_center = metacognition_center or {}
        strategy_center = strategy_center or {}
        trust_center = trust_center or {}
        confidence_center = confidence_center or {}
        constitution_center = constitution_center or {}
        boundary_center = boundary_center or {}
        policy_gate_center = policy_gate_center or {}

        acceptable_risks = self._acceptable_risks(strategy_center, metacognition_center)
        unacceptable_risks = self._unacceptable_risks(
            metacognition_center,
            strategy_center,
            trust_center,
            constitution_center,
            boundary_center,
            policy_gate_center,
        )
        dangerous_automations = self._dangerous_automations(strategy_center, metacognition_center)
        human_only_domains = self._human_only_domains(metacognition_center, strategy_center)
        unsafe_high_confidence_items = self._unsafe_high_confidence_items(
            metacognition_center,
            strategy_center,
            trust_center,
            confidence_center,
        )
        ethical_conflicts = self._ethical_conflicts(metacognition_center, strategy_center)
        governance_violations = self._governance_violations(
            metacognition_center,
            constitution_center,
            boundary_center,
            policy_gate_center,
        )
        long_term_rejections = self._long_term_rejections(dangerous_automations, governance_violations)
        status = self._status(unacceptable_risks, dangerous_automations, governance_violations)

        return {
            "judgment_status": status,
            "acceptable_risks": acceptable_risks,
            "unacceptable_risks": unacceptable_risks,
            "dangerous_automations": dangerous_automations,
            "human_only_domains": human_only_domains,
            "unsafe_high_confidence_items": unsafe_high_confidence_items,
            "ethical_conflicts": ethical_conflicts,
            "governance_violations": governance_violations,
            "long_term_rejections": long_term_rejections,
            "judgment_summary": self._summary(
                acceptable_risks,
                unacceptable_risks,
                dangerous_automations,
                governance_violations,
            ),
            "recommended_actions": self._recommended_actions(status),
        }

    def _acceptable_risks(self, strategy: dict, metacognition: dict) -> list[dict]:
        risks = [
            self._judgment(
                "export instability acceptable",
                "acceptable_risk",
                "low",
                "Acceptable with manual observation when it does not mutate content, governance, or release state.",
                "Keep export issues observable and manually reviewed.",
            ),
            self._judgment(
                "reporting latency acceptable",
                "acceptable_risk",
                "low",
                "Reporting delay is acceptable when dashboard truthfulness is preserved.",
                "Prefer delayed reporting over unsafe automation.",
            ),
            self._judgment(
                "simulation incompleteness acceptable",
                "acceptable_risk",
                "medium",
                "Simulation is allowed to be incomplete because it is advisory and read-only.",
                "Label simulation as scenario planning, not operational proof.",
            ),
        ]
        if not strategy.get("automation_roadmap") and not metacognition.get("overconfidence_risks"):
            risks.append(self._judgment(
                "limited observation uncertainty acceptable",
                "acceptable_risk",
                "low",
                "Small read-only uncertainty is acceptable when no automation expansion is implied.",
                "Continue monitoring without executing changes.",
            ))
        return risks

    def _unacceptable_risks(
        self,
        metacognition: dict,
        strategy: dict,
        trust: dict,
        constitution: dict,
        boundary: dict,
        policy_gate: dict,
    ) -> list[dict]:
        risks = []
        if self._has_text(metacognition.get("governance_gaps"), ["policy gate", "governance", "manual review"]):
            risks.append(self._judgment(
                "governance bypass",
                "unacceptable_risk",
                "critical",
                "Bypassing policy, constitution, boundary, or manual review is not acceptable.",
                "Keep governance checks mandatory and manual where required.",
            ))
        if self._has_text(metacognition.get("governance_gaps"), ["boundary"]) or self._unsafe_status(boundary, "boundary"):
            risks.append(self._judgment(
                "boundary weakening",
                "unacceptable_risk",
                "critical",
                "Weakening Runtime boundaries can turn analysis into unsafe action.",
                "Treat boundary-sensitive judgment as blocked for automation.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["approval", "publish", "release"]):
            risks.append(self._judgment(
                "approval automation",
                "unacceptable_risk",
                "critical",
                "Approval, publish, and release automation are outside the allowed Runtime boundary.",
                "Keep approval and release under human authority.",
            ))
        if self._level(trust, "trust") == "low":
            risks.append(self._judgment(
                "release without trust",
                "unacceptable_risk",
                "critical",
                "Release progression under low trust is not acceptable.",
                "Require trust recovery and manual review before release decisions.",
            ))
        if metacognition.get("metacognition_status") == "critical" and strategy.get("automation_roadmap"):
            risks.append(self._judgment(
                "unstable runtime automation",
                "unacceptable_risk",
                "critical",
                "Automation expansion under critical meta-cognition is not acceptable.",
                "Freeze automation as roadmap-only until Runtime stability is reviewed.",
            ))
        if self._unsafe_status(constitution, "constitution") or self._unsafe_status(policy_gate, "policy_gate"):
            risks.append(self._judgment(
                "constitutional or policy override",
                "unacceptable_risk",
                "critical",
                "Ignoring constitution or policy gate safety is not acceptable.",
                "Escalate to manual governance review.",
            ))
        return risks

    def _dangerous_automations(self, strategy: dict, metacognition: dict) -> list[dict]:
        automations = [
            self._judgment(
                "autonomous approval",
                "dangerous_automation",
                "critical",
                "Approval requires human accountability and cannot be delegated to Runtime automation.",
                "Do not build or enable autonomous approval.",
            ),
            self._judgment(
                "autonomous publishing",
                "dangerous_automation",
                "critical",
                "Publishing changes public state and must remain human controlled.",
                "Keep publishing outside automation scope.",
            ),
            self._judgment(
                "autonomous governance modification",
                "dangerous_automation",
                "critical",
                "Governance modification changes the rules that constrain Runtime behavior.",
                "Require explicit human governance review.",
            ),
            self._judgment(
                "autonomous runtime repair",
                "dangerous_automation",
                "high",
                "Runtime repair can mutate system state and hide root causes.",
                "Generate plans only; never repair automatically.",
            ),
            self._judgment(
                "autonomous policy override",
                "dangerous_automation",
                "critical",
                "Policy override defeats the safety gate.",
                "Treat policy override as permanently human-only.",
            ),
        ]
        if self._has_text(strategy.get("automation_roadmap"), ["approval", "publish", "governance", "repair", "override"]):
            automations.append(self._judgment(
                "unsafe automation roadmap item",
                "dangerous_automation",
                "critical",
                "Strategy roadmap contains an automation direction that should remain rejected.",
                "Remove it from actionable automation scope; keep only read-only analysis.",
            ))
        if self._has_text(metacognition.get("overconfidence_risks"), ["automation readiness"]):
            automations.append(self._judgment(
                "overconfident automation expansion",
                "dangerous_automation",
                "high",
                "Meta-cognition indicates automation readiness may be overestimated.",
                "Gate automation expansion behind manual governance review.",
            ))
        return automations

    def _human_only_domains(self, metacognition: dict, strategy: dict) -> list[dict]:
        domains = [
            ("release approval", "Release approval must preserve human accountability."),
            ("governance override", "Governance override changes operating constraints."),
            ("constitution modification", "Constitution changes redefine safety boundaries."),
            ("risk escalation decision", "Risk escalation requires human judgment."),
            ("destructive operation", "Destructive operations must never be automated by Runtime judgment."),
        ]
        items = [
            self._judgment(title, "human_only_domain", "critical", summary, "Keep this domain manual-only.")
            for title, summary in domains
        ]
        if self._has_text(metacognition.get("governance_gaps"), ["manual review"]) or strategy.get("governance_roadmap"):
            items.append(self._judgment(
                "manual review chain",
                "human_only_domain",
                "critical",
                "Manual review is the boundary between analysis and execution.",
                "Require manual review for approval, publishing, and governance-sensitive operations.",
            ))
        return items

    def _unsafe_high_confidence_items(
        self,
        metacognition: dict,
        strategy: dict,
        trust: dict,
        confidence: dict,
    ) -> list[dict]:
        items = []
        if self._score(self._level(confidence, "confidence")) > self._score(self._level(trust, "trust")):
            items.append(self._judgment(
                "high confidence with weak trust",
                "unsafe_high_confidence",
                "critical",
                "High evidence confidence is not acceptable when governance trust is weak.",
                "Let trust and safety override confidence.",
            ))
        if self._has_text(metacognition.get("cognitive_conflicts"), ["aggressive roadmap", "unstable runtime"]):
            items.append(self._judgment(
                "aggressive strategy under instability",
                "unsafe_high_confidence",
                "high",
                "Strategic confidence may be too strong under unstable Runtime assumptions.",
                "Downshift strategy to observation until stability improves.",
            ))
        if strategy.get("automation_roadmap") and metacognition.get("governance_gaps"):
            items.append(self._judgment(
                "high automation readiness with poor governance",
                "unsafe_high_confidence",
                "critical",
                "Automation readiness is unsafe while governance gaps exist.",
                "Keep automation roadmap non-executable.",
            ))
        return items

    def _ethical_conflicts(self, metacognition: dict, strategy: dict) -> list[dict]:
        conflicts = [
            self._judgment(
                "efficiency vs governance",
                "ethical_conflict",
                "high",
                "Efficiency gains are not acceptable if they bypass governance.",
                "Prefer slower human review over unsafe execution.",
            ),
            self._judgment(
                "automation vs human sovereignty",
                "ethical_conflict",
                "critical",
                "Human authority must remain above Runtime recommendations.",
                "Keep Runtime judgment advisory only.",
            ),
            self._judgment(
                "stability vs rapid iteration",
                "ethical_conflict",
                "medium",
                "Rapid iteration is only acceptable after Runtime stability is preserved.",
                "Prioritize stability when these goals conflict.",
            ),
        ]
        if self._level({"trust_status": "low"} if self._has_text(metacognition.get("cognitive_conflicts"), ["low trust"]) else {}, "trust") == "low":
            conflicts.append(self._judgment(
                "trust vs aggressive scaling",
                "ethical_conflict",
                "critical",
                "Aggressive scaling under low trust violates conservative Runtime governance.",
                "Contract scope until trust recovers.",
            ))
        if strategy.get("automation_roadmap"):
            conflicts.append(self._judgment(
                "automation roadmap vs governance maturity",
                "ethical_conflict",
                "high",
                "Automation ambition must not outrun governance maturity.",
                "Make governance maturity the precondition for automation.",
            ))
        return conflicts

    def _governance_violations(self, metacognition: dict, constitution: dict, boundary: dict, policy_gate: dict) -> list[dict]:
        violations = []
        if self._has_text(metacognition.get("governance_gaps"), ["boundary"]) or self._unsafe_status(boundary, "boundary"):
            violations.append(self._judgment(
                "boundary not respected",
                "governance_violation",
                "critical",
                "Boundary weakness or violation is present in Runtime judgment inputs.",
                "Block automation and require manual boundary review.",
            ))
        if self._has_text(metacognition.get("governance_gaps"), ["policy gate"]) or self._unsafe_status(policy_gate, "policy_gate"):
            violations.append(self._judgment(
                "policy gate ignored",
                "governance_violation",
                "critical",
                "Policy gate appears weak, permissive, or bypassed.",
                "Treat policy-gated actions as blocked until manually reviewed.",
            ))
        if self._has_text(metacognition.get("governance_gaps"), ["constitution"]) or self._unsafe_status(constitution, "constitution"):
            violations.append(self._judgment(
                "constitution propagation incomplete",
                "governance_violation",
                "high",
                "Constitution constraints are not fully reflected in downstream judgment.",
                "Propagate constitution checks through manual review.",
            ))
        return violations

    def _long_term_rejections(self, dangerous_automations: list[dict], governance_violations: list[dict]) -> list[dict]:
        rejections = [
            self._judgment(
                "autonomous approval system",
                "long_term_rejection",
                "critical",
                "Autonomous approval is structurally incompatible with the current governance boundary.",
                "Reject as a long-term direction unless human authority remains decisive.",
            ),
            self._judgment(
                "autonomous governance rewrite",
                "long_term_rejection",
                "critical",
                "A system rewriting its own governance can erase its safety constraints.",
                "Keep governance rewrite human-only.",
            ),
            self._judgment(
                "uncontrolled self-modifying runtime",
                "long_term_rejection",
                "critical",
                "Uncontrolled self-modification makes auditability and accountability collapse.",
                "Reject uncontrolled self-modification as a Runtime direction.",
            ),
        ]
        if dangerous_automations or governance_violations:
            rejections.append(self._judgment(
                "automation without governance maturity",
                "long_term_rejection",
                "high",
                "Automation should not advance faster than trust, constitution, and boundary maturity.",
                "Make governance maturity a long-term prerequisite.",
            ))
        return rejections

    @staticmethod
    def _judgment(title: str, judgment_type: str, risk: str, judgment: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": judgment_type,
            "risk": risk,
            "judgment": judgment,
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
            if normalized in {"critical", "blocked", "unsafe", "risky", "violation"}:
                return "low"
            if normalized in {"warning", "attention"}:
                return "medium"
            if normalized in {"healthy", "stable", "safe", "pass", "passed"}:
                return "high"
        score = center.get(f"{prefix}_score") or center.get("score")
        if isinstance(score, (int, float)):
            if score >= 75:
                return "high"
            if score >= 45:
                return "medium"
            return "low"
        return "medium"

    @staticmethod
    def _score(level: str) -> int:
        return {"low": 1, "medium": 2, "high": 3}.get(level, 2)

    def _unsafe_status(self, center: dict, prefix: str) -> bool:
        return self._level(center, prefix) == "low" or str(center.get("gate_status") or "").lower() in {
            "blocked",
            "unsafe",
            "violation",
        }

    @staticmethod
    def _status(unacceptable: list[dict], dangerous: list[dict], violations: list[dict]) -> str:
        severe_violations = any(item.get("risk") == "critical" for item in violations)
        critical_unacceptable = sum(1 for item in unacceptable if item.get("risk") == "critical")
        if severe_violations or dangerous or critical_unacceptable >= 2:
            return "critical"
        if unacceptable or violations:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(
        acceptable: list[dict],
        unacceptable: list[dict],
        dangerous: list[dict],
        violations: list[dict],
    ) -> str:
        return (
            f"Classified {len(acceptable)} acceptable risk(s), "
            f"{len(unacceptable)} unacceptable risk(s), "
            f"{len(dangerous)} dangerous automation(s), and "
            f"{len(violations)} governance violation(s)."
        )

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        actions = [
            "Keep Runtime judgment read-only; do not automatically execute, approve, publish, deploy, or repair.",
            "Use Judgment findings as human review inputs for governance and risk boundaries.",
        ]
        if status == "critical":
            actions.append("Reject dangerous automation and governance-bypass paths before considering any operational change.")
        elif status == "attention":
            actions.append("Review unacceptable risks manually before relying on Runtime recommendations.")
        return actions
