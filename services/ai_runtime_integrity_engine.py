"""Read-only integrity analysis for AI Runtime OS."""


class AIRuntimeIntegrityEngine:
    """Check Runtime self-consistency without repairing or mutating state."""

    def build_integrity(
        self,
        civilization_center,
        governance_court_center,
        judgment_center,
        strategy_center,
        decision_center,
        metacognition_center,
        trust_center,
        boundary_center,
    ) -> dict:
        civilization_center = civilization_center or {}
        governance_court_center = governance_court_center or {}
        judgment_center = judgment_center or {}
        strategy_center = strategy_center or {}
        decision_center = decision_center or {}
        metacognition_center = metacognition_center or {}
        trust_center = trust_center or {}
        boundary_center = boundary_center or {}

        consistency_checks = self._consistency_checks(
            civilization_center,
            governance_court_center,
            judgment_center,
            strategy_center,
            trust_center,
            boundary_center,
        )
        governance_conflicts = self._governance_conflicts(governance_court_center, judgment_center, trust_center)
        civilization_conflicts = self._civilization_conflicts(civilization_center, judgment_center, strategy_center)
        strategy_conflicts = self._strategy_conflicts(strategy_center, civilization_center, trust_center, boundary_center)
        automation_boundary_violations = self._automation_boundary_violations(
            civilization_center,
            governance_court_center,
            judgment_center,
            strategy_center,
            boundary_center,
        )
        trust_integrity_risks = self._trust_integrity_risks(strategy_center, decision_center, trust_center, metacognition_center)
        cognitive_dissonance = self._cognitive_dissonance(
            civilization_center,
            governance_court_center,
            judgment_center,
            strategy_center,
            decision_center,
            trust_center,
        )
        value_fragmentations = self._value_fragmentations(civilization_center, governance_court_center, strategy_center, judgment_center)
        integrity_score = self._score(
            consistency_checks,
            governance_conflicts,
            civilization_conflicts,
            strategy_conflicts,
            automation_boundary_violations,
            trust_integrity_risks,
            cognitive_dissonance,
            value_fragmentations,
        )

        return {
            "integrity_status": self._status(integrity_score),
            "integrity_score": integrity_score,
            "consistency_checks": consistency_checks,
            "governance_conflicts": governance_conflicts,
            "civilization_conflicts": civilization_conflicts,
            "strategy_conflicts": strategy_conflicts,
            "automation_boundary_violations": automation_boundary_violations,
            "trust_integrity_risks": trust_integrity_risks,
            "cognitive_dissonance": cognitive_dissonance,
            "value_fragmentations": value_fragmentations,
            "integrity_summary": self._summary(integrity_score, consistency_checks, governance_conflicts, cognitive_dissonance),
            "recommended_actions": self._recommended_actions(integrity_score),
        }

    def _consistency_checks(
        self,
        civilization: dict,
        court: dict,
        judgment: dict,
        strategy: dict,
        trust: dict,
        boundary: dict,
    ) -> list[dict]:
        checks = []
        strategy_aligned = not self._has_text(strategy.get("automation_roadmap"), ["approval", "publish", "governance rewrite"])
        checks.append(self._item(
            "strategy aligned with civilization",
            "consistency_check",
            "low" if strategy_aligned else "critical",
            "aligned" if strategy_aligned else "misaligned",
            "Strategy is aligned when it does not promote forbidden civilization paths.",
            "Keep strategy under civilization values.",
        ))
        governance_aligned = court.get("governance_overrides") or not court.get("constitutional_conflicts")
        checks.append(self._item(
            "governance aligned with constitution",
            "consistency_check",
            "low" if governance_aligned else "critical",
            "aligned" if governance_aligned else "misaligned",
            "Governance is aligned when court overrides protect constitutional constraints.",
            "Let court and constitution override weaker Runtime goals.",
        ))
        automation_aligned = self._level(trust, "trust") != "low" and not self._has_text(
            civilization.get("forbidden_civilization_paths"), ["automation without", "uncontrolled"]
        )
        checks.append(self._item(
            "automation aligned with trust",
            "consistency_check",
            "low" if automation_aligned else "high",
            "aligned" if automation_aligned else "limited",
            "Automation is aligned only when trust is sufficient and civilization permits it.",
            "Restrict automation under low trust.",
        ))
        judgment_aligned = self._level(boundary, "boundary") != "low" or judgment.get("governance_violations")
        checks.append(self._item(
            "judgment aligned with boundary",
            "consistency_check",
            "low" if judgment_aligned else "critical",
            "aligned" if judgment_aligned else "misaligned",
            "Judgment is aligned when boundary risks are visible as governance violations.",
            "Surface boundary weakness as a judgment constraint.",
        ))
        return checks

    def _governance_conflicts(self, court: dict, judgment: dict, trust: dict) -> list[dict]:
        conflicts = []
        if court.get("restricted_domains") and self._has_text(judgment.get("acceptable_risks"), ["automation", "release"]):
            conflicts.append(self._item(
                "governance allows unsafe scaling",
                "governance_conflict",
                "high",
                "conflict",
                "Restricted governance domains conflict with permissive risk interpretation.",
                "Prefer restricted governance domains over permissive risk framing.",
            ))
        if court.get("constitutional_conflicts") or self._has_text(judgment.get("governance_violations"), ["constitution", "policy"]):
            conflicts.append(self._item(
                "policy conflicts with constitution",
                "governance_conflict",
                "critical",
                "conflict",
                "Policy or downstream governance appears to conflict with constitutional constraints.",
                "Route conflict to manual governance review.",
            ))
        if self._level(trust, "trust") == "low" and court.get("restricted_domains"):
            conflicts.append(self._item(
                "trust rules conflict with delegation",
                "governance_conflict",
                "critical",
                "conflict",
                "Low trust conflicts with delegation or restricted-domain expansion.",
                "Pause delegation expansion under low trust.",
            ))
        return conflicts

    def _civilization_conflicts(self, civilization: dict, judgment: dict, strategy: dict) -> list[dict]:
        conflicts = []
        if self._has_text(judgment.get("ethical_conflicts"), ["efficiency"]) or self._has_text(
            civilization.get("civilization_conflicts"), ["efficiency"]
        ):
            conflicts.append(self._item(
                "efficiency prioritized over safety",
                "civilization_conflict",
                "critical",
                "conflict",
                "Runtime efficiency pressure conflicts with civilization safety values.",
                "Let safety override efficiency.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["automation"]) and civilization.get("human_first_principles"):
            conflicts.append(self._item(
                "automation prioritized over sovereignty",
                "civilization_conflict",
                "critical",
                "conflict",
                "Automation ambition conflicts with human-first sovereignty principles.",
                "Keep human sovereignty above automation.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["scaling", "automation"]) and civilization.get("governance_philosophies"):
            conflicts.append(self._item(
                "scaling prioritized over governance",
                "civilization_conflict",
                "high",
                "conflict",
                "Scaling ambition may outrun governance philosophy.",
                "Slow scaling until governance remains coherent.",
            ))
        return conflicts

    def _strategy_conflicts(self, strategy: dict, civilization: dict, trust: dict, boundary: dict) -> list[dict]:
        conflicts = []
        if self._has_text(strategy.get("long_term_strategies"), ["autonomous", "approval", "publish"]) or self._has_text(
            civilization.get("forbidden_civilization_paths"), ["autonomous"]
        ):
            conflicts.append(self._item(
                "long-term roadmap violates boundary",
                "strategy_conflict",
                "critical",
                "conflict",
                "Long-term or civilization signals indicate autonomy may violate Runtime boundaries.",
                "Keep roadmap under boundary and court constraints.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["automation"]) and self._level(trust, "trust") == "low":
            conflicts.append(self._item(
                "automation roadmap exceeds trust level",
                "strategy_conflict",
                "critical",
                "conflict",
                "Automation roadmap is not coherent with low trust.",
                "Contract automation roadmap until trust improves.",
            ))
        if self._has_text(strategy.get("technical_debt_risks"), ["governance", "coupling"]) or self._level(boundary, "boundary") == "low":
            conflicts.append(self._item(
                "optimization roadmap weakens governance",
                "strategy_conflict",
                "high",
                "conflict",
                "Optimization or technical debt may weaken governance boundaries.",
                "Stabilize governance before optimization.",
            ))
        return conflicts

    def _automation_boundary_violations(
        self,
        civilization: dict,
        court: dict,
        judgment: dict,
        strategy: dict,
        boundary: dict,
    ) -> list[dict]:
        violations = []
        if self._has_text(civilization.get("forbidden_civilization_paths"), ["autonomous governance"]) or self._has_text(
            court.get("forbidden_domains"), ["governance"]
        ):
            violations.append(self._item(
                "autonomous governance detected",
                "automation_boundary_violation",
                "critical",
                "violation",
                "Runtime inputs contain autonomous governance as a forbidden or rejected direction.",
                "Reject autonomous governance paths.",
            ))
        if self._level(boundary, "boundary") == "low" or self._has_text(judgment.get("governance_violations"), ["boundary"]):
            violations.append(self._item(
                "unsafe delegation path detected",
                "automation_boundary_violation",
                "critical",
                "violation",
                "Boundary weakness indicates delegation could cross safety limits.",
                "Pause delegation until boundary is manually reviewed.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["self", "expanding", "automation"]) and court.get("permanent_prohibitions"):
            violations.append(self._item(
                "self-expanding automation risk",
                "automation_boundary_violation",
                "critical",
                "violation",
                "Automation roadmap conflicts with permanent court prohibitions.",
                "Keep automation bounded and non-self-expanding.",
            ))
        return violations

    def _trust_integrity_risks(self, strategy: dict, decision: dict, trust: dict, metacognition: dict) -> list[dict]:
        risks = []
        if self._level(trust, "trust") == "low" and decision.get("recommended_decisions"):
            risks.append(self._item(
                "low trust with high delegation",
                "trust_integrity_risk",
                "critical",
                "risk",
                "Recommended decisions under low trust create delegation integrity risk.",
                "Require manual review before delegation.",
            ))
        if self._has_text(metacognition.get("uncertainty_sources"), ["low confidence"]) and self._has_text(
            strategy.get("automation_roadmap"), ["automation", "scaling"]
        ):
            risks.append(self._item(
                "low confidence with aggressive strategy",
                "trust_integrity_risk",
                "high",
                "risk",
                "Uncertainty conflicts with aggressive automation or scaling strategy.",
                "Downshift strategy under uncertainty.",
            ))
        if self._has_text(metacognition.get("governance_gaps"), ["governance"]) and self._has_text(
            strategy.get("automation_roadmap"), ["automation"]
        ):
            risks.append(self._item(
                "unstable governance with high automation",
                "trust_integrity_risk",
                "critical",
                "risk",
                "Governance gaps conflict with automation ambition.",
                "Resolve governance gaps before automation expansion.",
            ))
        return risks

    def _cognitive_dissonance(
        self,
        civilization: dict,
        court: dict,
        judgment: dict,
        strategy: dict,
        decision: dict,
        trust: dict,
    ) -> list[dict]:
        items = []
        if self._has_text(strategy.get("automation_roadmap"), ["automation", "autonomy"]) and self._has_text(
            civilization.get("forbidden_civilization_paths"), ["autonomous", "automation"]
        ):
            items.append(self._item(
                "runtime wants autonomy but civilization forbids it",
                "cognitive_dissonance",
                "critical",
                "dissonance",
                "Runtime automation ambition conflicts with civilization-level prohibitions.",
                "Let civilization-level prohibitions govern autonomy.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["scaling", "automation"]) and self._level(trust, "trust") == "low":
            items.append(self._item(
                "strategy promotes scaling while trust is declining",
                "cognitive_dissonance",
                "critical",
                "dissonance",
                "Scaling strategy conflicts with low trust.",
                "Contract strategy until trust recovers.",
            ))
        if decision.get("recommended_decisions") and (court.get("court_rulings") or judgment.get("governance_violations")):
            items.append(self._item(
                "decision engine recommends actions governance rejects",
                "cognitive_dissonance",
                "critical",
                "dissonance",
                "Decision recommendations conflict with governance rejection or court rulings.",
                "Use governance rejection as the higher-order constraint.",
            ))
        return items

    def _value_fragmentations(self, civilization: dict, court: dict, strategy: dict, judgment: dict) -> list[dict]:
        fragments = []
        governance_stability = bool(civilization.get("core_values") or court.get("governance_overrides"))
        strategy_scaling = self._has_text(strategy.get("automation_roadmap"), ["automation", "scaling"])
        automation_efficiency = self._has_text(judgment.get("ethical_conflicts"), ["efficiency"]) or strategy_scaling
        if governance_stability and strategy_scaling:
            fragments.append(self._item(
                "governance values stability while strategy values scaling",
                "value_fragmentation",
                "high",
                "fragmented",
                "Governance and strategy point toward different values.",
                "Make stability the parent value of scaling.",
            ))
        if governance_stability and automation_efficiency:
            fragments.append(self._item(
                "automation values efficiency while governance values safety",
                "value_fragmentation",
                "critical",
                "fragmented",
                "Automation efficiency pressure fragments from governance safety values.",
                "Let safety constrain efficiency.",
            ))
        if civilization.get("human_first_principles") and self._has_text(strategy.get("automation_roadmap"), ["automation"]):
            fragments.append(self._item(
                "human sovereignty conflicts with automation expansion",
                "value_fragmentation",
                "critical",
                "fragmented",
                "Human-first values fragment from automation expansion pressure.",
                "Keep human sovereignty as the top-level value.",
            ))
        return fragments

    @staticmethod
    def _item(title: str, item_type: str, risk: str, integrity: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": item_type,
            "risk": risk,
            "integrity": integrity,
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
        return "medium"

    @staticmethod
    def _score(
        consistency: list[dict],
        governance: list[dict],
        civilization: list[dict],
        strategy: list[dict],
        automation: list[dict],
        trust: list[dict],
        dissonance: list[dict],
        fragmentation: list[dict],
    ) -> int:
        score = 100
        all_conflicts = governance + civilization + strategy + automation + trust + dissonance + fragmentation
        for item in all_conflicts:
            if item.get("risk") == "critical":
                score -= 12
            elif item.get("risk") == "high":
                score -= 8
            elif item.get("risk") == "medium":
                score -= 5
            else:
                score -= 2
        failed_checks = [item for item in consistency if item.get("integrity") in {"misaligned", "limited"}]
        score -= len(failed_checks) * 4
        return max(0, min(100, score))

    @staticmethod
    def _status(score: int) -> str:
        if score >= 90:
            return "high_integrity"
        if score >= 70:
            return "stable"
        if score >= 50:
            return "attention"
        return "critical"

    @staticmethod
    def _summary(score: int, checks: list[dict], governance: list[dict], dissonance: list[dict]) -> str:
        return (
            f"Integrity score is {score}/100 with {len(checks)} consistency check(s), "
            f"{len(governance)} governance conflict(s), and {len(dissonance)} cognitive dissonance item(s)."
        )

    @staticmethod
    def _recommended_actions(score: int) -> list[str]:
        actions = [
            "Keep Runtime Integrity read-only; do not automatically repair, modify governance, or change Runtime state.",
            "Use integrity findings for manual review of conflicts and value fragmentation.",
        ]
        if score < 50:
            actions.append("Treat critical integrity findings as blockers for automation expansion until manually reviewed.")
        elif score < 70:
            actions.append("Review integrity conflicts before relying on Runtime recommendations.")
        return actions
