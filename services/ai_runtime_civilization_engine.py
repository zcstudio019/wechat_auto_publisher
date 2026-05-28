"""Read-only civilization analysis for AI Runtime OS."""


class AIRuntimeCivilizationEngine:
    """Build Runtime civilization principles without executing or mutating state."""

    def build_civilization(
        self,
        governance_court_center,
        constitution_center,
        judgment_center,
        metacognition_center,
        strategy_center,
        memory_center,
    ) -> dict:
        governance_court_center = governance_court_center or {}
        constitution_center = constitution_center or {}
        judgment_center = judgment_center or {}
        metacognition_center = metacognition_center or {}
        strategy_center = strategy_center or {}
        memory_center = memory_center or {}

        core_values = self._core_values(governance_court_center, judgment_center)
        human_first_principles = self._human_first_principles(governance_court_center, judgment_center)
        civilization_priorities = self._civilization_priorities(strategy_center, memory_center)
        forbidden_civilization_paths = self._forbidden_civilization_paths(governance_court_center, judgment_center)
        long_term_survival_principles = self._long_term_survival_principles(memory_center, metacognition_center)
        governance_philosophies = self._governance_philosophies(governance_court_center, constitution_center)
        runtime_identity = self._runtime_identity(core_values, governance_court_center)
        civilization_conflicts = self._civilization_conflicts(
            governance_court_center,
            judgment_center,
            metacognition_center,
            strategy_center,
        )
        status = self._status(forbidden_civilization_paths, governance_philosophies, civilization_conflicts)

        return {
            "civilization_status": status,
            "core_values": core_values,
            "human_first_principles": human_first_principles,
            "civilization_priorities": civilization_priorities,
            "forbidden_civilization_paths": forbidden_civilization_paths,
            "long_term_survival_principles": long_term_survival_principles,
            "governance_philosophies": governance_philosophies,
            "runtime_identity": runtime_identity,
            "civilization_conflicts": civilization_conflicts,
            "civilization_summary": self._summary(
                core_values,
                human_first_principles,
                forbidden_civilization_paths,
                runtime_identity,
                civilization_conflicts,
            ),
            "recommended_actions": self._recommended_actions(status),
        }

    def _core_values(self, court: dict, judgment: dict) -> list[dict]:
        values = [
            self._principle(
                "safety before automation",
                "core_value",
                "critical",
                "Safety is the first value when automation creates irreversible or governance-sensitive effects.",
                "Keep automation subordinate to safety.",
            ),
            self._principle(
                "governance before scaling",
                "core_value",
                "critical",
                "Scaling without governance maturity amplifies systemic risk.",
                "Mature governance before expanding Runtime capability.",
            ),
            self._principle(
                "trust before delegation",
                "core_value",
                "high",
                "Delegation is only acceptable after trust is stable and auditable.",
                "Use trust as a precondition for delegation.",
            ),
            self._principle(
                "human sovereignty above efficiency",
                "core_value",
                "critical",
                "Efficiency must not outrank human authority over release, governance, and destructive actions.",
                "Let human sovereignty override efficiency.",
            ),
        ]
        if court.get("court_status") == "critical" or judgment.get("judgment_status") == "critical":
            values.append(self._principle(
                "rule of law above runtime ambition",
                "core_value",
                "critical",
                "Court and judgment risks mean the Runtime must accept constitutional limits.",
                "Constrain Runtime ambition under governance law.",
            ))
        return values

    def _human_first_principles(self, court: dict, judgment: dict) -> list[dict]:
        principles = [
            self._principle(
                "human approval required",
                "human_first",
                "critical",
                "Approval authority belongs to accountable humans.",
                "Keep approval manual.",
            ),
            self._principle(
                "destructive actions require humans",
                "human_first",
                "critical",
                "Destructive operations need accountable human judgment.",
                "Never automate destructive operations.",
            ),
            self._principle(
                "governance cannot be autonomous",
                "human_first",
                "critical",
                "Runtime must not autonomously rewrite the rules that govern it.",
                "Keep governance changes human-owned.",
            ),
            self._principle(
                "release authority belongs to humans",
                "human_first",
                "critical",
                "Release authority changes operational reality and must remain human-owned.",
                "Require human release authorization.",
            ),
        ]
        if court.get("human_sovereignty_domains") or judgment.get("human_only_domains"):
            principles.append(self._principle(
                "human sovereignty is final",
                "human_first",
                "critical",
                "Human sovereignty domains remain above Runtime recommendations.",
                "Treat Runtime outputs as advisory.",
            ))
        return principles

    def _civilization_priorities(self, strategy: dict, memory: dict) -> list[dict]:
        priorities = [
            self._priority("P0", "runtime stability", "critical", "A civilization layer cannot survive on unstable Runtime foundations."),
            self._priority("P1", "governance integrity", "critical", "Governance integrity keeps the Runtime bounded and accountable."),
            self._priority("P2", "trustworthiness", "high", "Trustworthiness is the basis for safe delegation and long-term operation."),
            self._priority("P3", "automation maturity", "medium", "Automation maturity follows stability, governance, and trust."),
        ]
        if self._has_text(strategy.get("technical_debt_risks"), ["JSON", "coupling", "export"]) or memory.get("repeated_patterns"):
            priorities.append(self._priority(
                "P0",
                "risk contraction",
                "critical",
                "Recurring instability and technical debt must be contracted before capability expansion.",
            ))
        return priorities

    def _forbidden_civilization_paths(self, court: dict, judgment: dict) -> list[dict]:
        paths = [
            self._principle(
                "autonomous governance civilization",
                "forbidden_path",
                "critical",
                "A Runtime civilization cannot allow autonomous governance rewrite.",
                "Reject autonomous governance as a civilization path.",
            ),
            self._principle(
                "self modifying runtime civilization",
                "forbidden_path",
                "critical",
                "Unbounded self-modification dissolves auditability and identity.",
                "Reject uncontrolled self-modifying Runtime.",
            ),
            self._principle(
                "uncontrolled optimization civilization",
                "forbidden_path",
                "critical",
                "Optimization without governance can optimize away safety and accountability.",
                "Bind optimization under governance principles.",
            ),
            self._principle(
                "efficiency over safety civilization",
                "forbidden_path",
                "critical",
                "A system that values efficiency over safety becomes unsafe by design.",
                "Keep safety above efficiency.",
            ),
        ]
        if court.get("permanent_prohibitions") or judgment.get("long_term_rejections"):
            paths.append(self._principle(
                "automation without rule of law civilization",
                "forbidden_path",
                "critical",
                "Permanent prohibitions indicate automation must remain bounded by rule of law.",
                "Do not evolve Runtime toward unbounded automation.",
            ))
        return paths

    def _long_term_survival_principles(self, memory: dict, metacognition: dict) -> list[dict]:
        principles = [
            self._principle(
                "stable systems survive longer",
                "survival_principle",
                "high",
                "Runtime stability extends operational life more than rapid capability expansion.",
                "Prioritize stability investment.",
            ),
            self._principle(
                "governance debt destroys systems",
                "survival_principle",
                "critical",
                "Governance debt compounds faster than feature debt under automation pressure.",
                "Pay down governance debt before automation expansion.",
            ),
            self._principle(
                "trust erosion precedes collapse",
                "survival_principle",
                "critical",
                "Low trust is an early signal of systemic fragility.",
                "Contract scope when trust degrades.",
            ),
            self._principle(
                "over-automation increases fragility",
                "survival_principle",
                "high",
                "Automation can turn local errors into systemic failures.",
                "Keep automation bounded and reversible.",
            ),
        ]
        if memory.get("memory_status") == "critical" or metacognition.get("metacognition_status") == "critical":
            principles.append(self._principle(
                "self-awareness precedes survival",
                "survival_principle",
                "high",
                "The Runtime must understand its own blind spots before expanding capability.",
                "Review meta-cognition before strategy execution.",
            ))
        return principles

    def _governance_philosophies(self, court: dict, constitution: dict) -> list[dict]:
        philosophies = [
            self._principle(
                "slow governance beats aggressive scaling",
                "governance_philosophy",
                "high",
                "Careful governance keeps the Runtime alive longer than fast scaling.",
                "Scale only after governance review.",
            ),
            self._principle(
                "constitutional systems outlive optimization systems",
                "governance_philosophy",
                "critical",
                "Systems with explicit constitutional constraints preserve identity and safety.",
                "Let constitutional principles outrank optimization.",
            ),
            self._principle(
                "bounded autonomy safer than unlimited autonomy",
                "governance_philosophy",
                "critical",
                "Bounded autonomy can be audited; unlimited autonomy cannot.",
                "Keep autonomy bounded by court, constitution, boundary, and human sovereignty.",
            ),
        ]
        if court.get("governance_overrides") or self._unsafe_status(constitution, "constitution"):
            philosophies.append(self._principle(
                "rule of law precedes delegation",
                "governance_philosophy",
                "critical",
                "Delegation is safe only under Runtime rule of law.",
                "Constrain delegation with governance court rulings.",
            ))
        return philosophies

    def _runtime_identity(self, core_values: list[dict], court: dict) -> list[dict]:
        identity = [
            self._principle(
                "governance-first runtime",
                "runtime_identity",
                "critical",
                "The Runtime defines itself by governance constraints before operational power.",
                "Use governance-first identity as the primary operating posture.",
            ),
            self._principle(
                "human-supervised runtime",
                "runtime_identity",
                "critical",
                "The Runtime exists under human supervision and accountability.",
                "Preserve human supervision across release, governance, and destructive domains.",
            ),
            self._principle(
                "bounded-autonomy runtime",
                "runtime_identity",
                "high",
                "The Runtime may analyze broadly but must act only within bounded, human-approved domains.",
                "Keep autonomy advisory unless explicitly authorized by humans.",
            ),
            self._principle(
                "safety-oriented runtime OS",
                "runtime_identity",
                "critical",
                "The Runtime OS is oriented toward safety, stability, and accountability.",
                "Prefer safe latency over unsafe speed.",
            ),
        ]
        if core_values and court.get("court_status") == "critical":
            identity.append(self._principle(
                "court-constrained runtime civilization",
                "runtime_identity",
                "critical",
                "The Governance Court defines the final boundary of Runtime civilization.",
                "Treat court boundaries as final advisory limits.",
            ))
        return identity

    def _civilization_conflicts(self, court: dict, judgment: dict, metacognition: dict, strategy: dict) -> list[dict]:
        conflicts = []
        if self._has_text(judgment.get("ethical_conflicts"), ["efficiency"]) or court.get("forbidden_domains"):
            conflicts.append(self._principle(
                "efficiency conflicts with governance",
                "civilization_conflict",
                "critical",
                "Efficiency gains can conflict with governance boundaries.",
                "Let governance override efficiency.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["automation", "scaling"]) and self._has_text(
            metacognition.get("overconfidence_risks"), ["trust", "automation"]
        ):
            conflicts.append(self._principle(
                "scaling conflicts with trust",
                "civilization_conflict",
                "critical",
                "Scaling ambition conflicts with trust and overconfidence warnings.",
                "Contract scaling until trust improves.",
            ))
        if court.get("constitutional_conflicts") or self._has_text(judgment.get("dangerous_automations"), ["autonomous"]):
            conflicts.append(self._principle(
                "autonomy conflicts with constitution",
                "civilization_conflict",
                "critical",
                "Autonomy becomes unsafe when it conflicts with constitution or court rulings.",
                "Let constitution and court override autonomy.",
            ))
        if self._has_text(strategy.get("technical_debt_risks"), ["coupling", "JSON", "export"]) or self._has_text(
            metacognition.get("fragile_assumptions"), ["stable", "deterministic", "causal"]
        ):
            conflicts.append(self._principle(
                "optimization conflicts with stability",
                "civilization_conflict",
                "high",
                "Optimization can worsen fragile technical and cognitive assumptions.",
                "Stabilize foundations before optimization.",
            ))
        return conflicts

    @staticmethod
    def _principle(title: str, principle_type: str, risk: str, philosophy: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": principle_type,
            "risk": risk,
            "philosophy": philosophy,
            "recommendation": recommendation,
        }

    @staticmethod
    def _priority(priority: str, title: str, risk: str, philosophy: str) -> dict:
        return {
            "title": title,
            "type": "civilization_priority",
            "priority": priority,
            "risk": risk,
            "philosophy": philosophy,
            "recommendation": f"Keep {priority} as a Runtime civilization priority.",
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
        return "medium"

    def _unsafe_status(self, center: dict, prefix: str) -> bool:
        return self._level(center, prefix) == "low" or str(center.get("gate_status") or "").lower() in {
            "blocked",
            "unsafe",
            "violation",
            "denied",
        }

    @staticmethod
    def _status(forbidden_paths: list[dict], philosophies: list[dict], conflicts: list[dict]) -> str:
        severe_conflicts = sum(1 for item in conflicts if item.get("risk") == "critical")
        if forbidden_paths or severe_conflicts >= 2:
            return "critical"
        if not philosophies or conflicts:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(
        core_values: list[dict],
        human_first: list[dict],
        forbidden_paths: list[dict],
        identity: list[dict],
        conflicts: list[dict],
    ) -> str:
        return (
            f"Civilization layer defines {len(core_values)} core value(s), "
            f"{len(human_first)} human-first principle(s), "
            f"{len(forbidden_paths)} forbidden path(s), "
            f"{len(identity)} identity statement(s), and "
            f"{len(conflicts)} civilization conflict(s)."
        )

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        actions = [
            "Keep Runtime Civilization read-only; do not automatically modify governance, constitution, strategy, or Runtime state.",
            "Use Civilization findings as long-term human review guidance, not executable policy.",
        ]
        if status == "critical":
            actions.append("Reject forbidden civilization paths before expanding automation or delegation.")
        elif status == "attention":
            actions.append("Review civilization conflicts before relying on Runtime strategic recommendations.")
        return actions
