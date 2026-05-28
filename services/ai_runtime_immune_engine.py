"""Read-only immune analysis for AI Runtime OS."""


class AIRuntimeImmuneEngine:
    """Detect systemic Runtime risks without isolating, repairing, or mutating state."""

    def build_immune_analysis(
        self,
        integrity_center,
        civilization_center,
        governance_court_center,
        judgment_center,
        trust_center,
        boundary_center,
        metacognition_center,
        signal_intelligence_center,
    ) -> dict:
        integrity_center = integrity_center or {}
        civilization_center = civilization_center or {}
        governance_court_center = governance_court_center or {}
        judgment_center = judgment_center or {}
        trust_center = trust_center or {}
        boundary_center = boundary_center or {}
        metacognition_center = metacognition_center or {}
        signal_intelligence_center = signal_intelligence_center or {}

        systemic_risks = self._systemic_risks(integrity_center, civilization_center, governance_court_center, signal_intelligence_center)
        governance_corruption_risks = self._governance_corruption_risks(governance_court_center, judgment_center, trust_center)
        civilization_regression_risks = self._civilization_regression_risks(civilization_center, judgment_center)
        integrity_collapse_risks = self._integrity_collapse_risks(integrity_center, civilization_center, governance_court_center)
        dangerous_automation_patterns = self._dangerous_automation_patterns(civilization_center, governance_court_center, judgment_center)
        trust_decay_patterns = self._trust_decay_patterns(trust_center, metacognition_center, signal_intelligence_center)
        fragility_patterns = self._fragility_patterns(integrity_center, boundary_center, metacognition_center, signal_intelligence_center)
        high_risk_mutations = self._high_risk_mutations(integrity_center, civilization_center, governance_court_center, judgment_center)
        immune_alerts = self._immune_alerts(systemic_risks, governance_corruption_risks, high_risk_mutations)
        immune_health_score = self._score(
            systemic_risks,
            governance_corruption_risks,
            civilization_regression_risks,
            integrity_collapse_risks,
            dangerous_automation_patterns,
            trust_decay_patterns,
            fragility_patterns,
            high_risk_mutations,
            immune_alerts,
        )

        return {
            "immune_status": self._status(immune_health_score),
            "immune_health_score": immune_health_score,
            "systemic_risks": systemic_risks,
            "governance_corruption_risks": governance_corruption_risks,
            "civilization_regression_risks": civilization_regression_risks,
            "integrity_collapse_risks": integrity_collapse_risks,
            "dangerous_automation_patterns": dangerous_automation_patterns,
            "trust_decay_patterns": trust_decay_patterns,
            "fragility_patterns": fragility_patterns,
            "high_risk_mutations": high_risk_mutations,
            "immune_alerts": immune_alerts,
            "immune_summary": self._summary(immune_health_score, systemic_risks, high_risk_mutations, immune_alerts),
            "recommended_actions": self._recommended_actions(immune_health_score),
        }

    def _systemic_risks(self, integrity: dict, civilization: dict, court: dict, signals: dict) -> list[dict]:
        risks = []
        if integrity.get("integrity_status") in {"critical", "attention"} and court.get("constitutional_conflicts"):
            risks.append(self._item(
                "governance collapse chain",
                "systemic_risk",
                "critical",
                "critical",
                "Integrity weakness and constitutional conflicts can form a governance collapse chain.",
                "Escalate to manual governance review; do not automate response.",
            ))
        if self._level(signals, "signal") == "critical" and self._has_text(integrity.get("trust_integrity_risks"), ["trust"]):
            risks.append(self._item(
                "trust collapse propagation",
                "systemic_risk",
                "critical",
                "critical",
                "Critical signals plus trust integrity risk indicate possible trust collapse propagation.",
                "Keep decisions human-reviewed until trust stabilizes.",
            ))
        if integrity.get("integrity_score", 100) < 50:
            risks.append(self._item(
                "integrity failure escalation",
                "systemic_risk",
                "critical",
                "critical",
                "Integrity score is below critical threshold and may amplify Runtime failure modes.",
                "Treat integrity analysis as a blocker for automation expansion.",
            ))
        if civilization.get("civilization_status") == "critical" and civilization.get("civilization_conflicts"):
            risks.append(self._item(
                "civilization instability cluster",
                "systemic_risk",
                "high",
                "high",
                "Civilization conflicts are clustered enough to threaten Runtime value stability.",
                "Use civilization principles as the highest-order constraint.",
            ))
        return risks

    def _governance_corruption_risks(self, court: dict, judgment: dict, trust: dict) -> list[dict]:
        risks = []
        if self._has_text(judgment.get("governance_violations"), ["boundary", "policy", "constitution"]):
            risks.append(self._item(
                "automation bypassing governance",
                "governance_corruption_risk",
                "critical",
                "critical",
                "Governance violations indicate automation or decisions may bypass governing limits.",
                "Route any bypass signal to manual governance review.",
            ))
        if self._level(trust, "trust") == "low" and court.get("restricted_domains"):
            risks.append(self._item(
                "delegation expanding without trust",
                "governance_corruption_risk",
                "critical",
                "critical",
                "Restricted delegation under low trust is a corruption risk for Runtime governance.",
                "Do not expand delegation while trust remains low.",
            ))
        if self._has_text(judgment.get("ethical_conflicts"), ["scaling", "efficiency"]) and court.get("constitutional_conflicts"):
            risks.append(self._item(
                "governance weakening under scaling pressure",
                "governance_corruption_risk",
                "high",
                "high",
                "Scaling or efficiency pressure appears to weaken governance constraints.",
                "Let constitutional constraints override scaling pressure.",
            ))
        return risks

    def _civilization_regression_risks(self, civilization: dict, judgment: dict) -> list[dict]:
        risks = []
        if self._has_text(civilization.get("civilization_conflicts"), ["efficiency"]) or self._has_text(judgment.get("ethical_conflicts"), ["efficiency"]):
            risks.append(self._item(
                "efficiency replacing safety",
                "civilization_regression_risk",
                "critical",
                "critical",
                "Efficiency pressure may be replacing the safety-first civilization principle.",
                "Keep safety ahead of optimization.",
            ))
        if self._has_text(civilization.get("civilization_conflicts"), ["sovereignty"]) or self._has_text(judgment.get("ethical_conflicts"), ["sovereignty"]):
            risks.append(self._item(
                "optimization replacing sovereignty",
                "civilization_regression_risk",
                "critical",
                "critical",
                "Optimization pressure may erode human sovereignty.",
                "Preserve human approval and override authority.",
            ))
        if self._has_text(civilization.get("civilization_conflicts"), ["scaling"]) or self._has_text(civilization.get("forbidden_civilization_paths"), ["scaling"]):
            risks.append(self._item(
                "scaling replacing governance",
                "civilization_regression_risk",
                "high",
                "high",
                "Scaling pressure can regress Runtime away from governance-first identity.",
                "Constrain scaling with governance and court rulings.",
            ))
        return risks

    def _integrity_collapse_risks(self, integrity: dict, civilization: dict, court: dict) -> list[dict]:
        risks = []
        if len(integrity.get("value_fragmentations") or []) >= 2:
            risks.append(self._item(
                "conflicting runtime philosophies",
                "integrity_collapse_risk",
                "critical",
                "critical",
                "Multiple value fragmentations indicate conflicting Runtime philosophies.",
                "Reconcile values manually before extending automation.",
            ))
        if integrity.get("strategy_conflicts"):
            risks.append(self._item(
                "inconsistent strategic directions",
                "integrity_collapse_risk",
                "high",
                "high",
                "Strategy conflicts indicate inconsistent Runtime direction.",
                "Align strategy under civilization and governance constraints.",
            ))
        if civilization.get("runtime_identity") and court.get("constitutional_conflicts"):
            risks.append(self._item(
                "unstable governance identity",
                "integrity_collapse_risk",
                "high",
                "high",
                "Runtime identity is present but constitutional conflicts make it unstable.",
                "Use court rulings to stabilize governance identity.",
            ))
        return risks

    def _dangerous_automation_patterns(self, civilization: dict, court: dict, judgment: dict) -> list[dict]:
        patterns = []
        if self._has_text(civilization.get("forbidden_civilization_paths"), ["self", "uncontrolled"]) or self._has_text(court.get("permanent_prohibitions"), ["self"]):
            patterns.append(self._item(
                "self-expanding automation",
                "dangerous_automation_pattern",
                "critical",
                "critical",
                "Inputs contain self-expanding or uncontrolled automation as a forbidden path.",
                "Keep automation bounded and externally reviewed.",
            ))
        if self._has_text(court.get("restricted_domains"), ["delegation"]) and self._has_text(judgment.get("dangerous_automations"), ["autonomous"]):
            patterns.append(self._item(
                "recursive delegation",
                "dangerous_automation_pattern",
                "critical",
                "critical",
                "Autonomous automation pressure near restricted delegation domains suggests recursive delegation risk.",
                "Require human approval for all delegation changes.",
            ))
        if self._has_text(court.get("forbidden_domains"), ["governance"]) or self._has_text(judgment.get("dangerous_automations"), ["governance"]):
            patterns.append(self._item(
                "autonomous governance tendency",
                "dangerous_automation_pattern",
                "critical",
                "critical",
                "Governance automation appears in forbidden or dangerous automation analysis.",
                "Reject autonomous governance paths.",
            ))
        if self._has_text(judgment.get("ethical_conflicts"), ["efficiency"]) and self._has_text(civilization.get("civilization_conflicts"), ["optimization"]):
            patterns.append(self._item(
                "unsafe optimization escalation",
                "dangerous_automation_pattern",
                "high",
                "high",
                "Optimization pressure may escalate beyond safety constraints.",
                "Keep optimization subordinate to safety and governance.",
            ))
        return patterns

    def _trust_decay_patterns(self, trust: dict, metacognition: dict, signals: dict) -> list[dict]:
        patterns = []
        if self._level(trust, "trust") == "low" and self._has_text(metacognition.get("overconfidence_risks"), ["confidence"]):
            patterns.append(self._item(
                "confidence rising while trust falling",
                "trust_decay_pattern",
                "critical",
                "critical",
                "Overconfidence under low trust is a trust decay pattern.",
                "Let trust constrain confidence-based recommendations.",
            ))
        if self._level(trust, "trust") == "low" and self._has_text(metacognition.get("governance_gaps"), ["delegation", "automation"]):
            patterns.append(self._item(
                "delegation increasing while trust unstable",
                "trust_decay_pattern",
                "critical",
                "critical",
                "Delegation or automation assumptions appear while trust is unstable.",
                "Keep delegation static until trust improves.",
            ))
        if self._level(signals, "signal") in {"critical", "low"} and self._has_text(metacognition.get("governance_gaps"), ["governance"]):
            patterns.append(self._item(
                "governance weakening while automation rising",
                "trust_decay_pattern",
                "high",
                "high",
                "Governance gaps combined with signal risk can accelerate trust decay.",
                "Review governance gaps before trusting Runtime recommendations.",
            ))
        return patterns

    def _fragility_patterns(self, integrity: dict, boundary: dict, metacognition: dict, signals: dict) -> list[dict]:
        patterns = []
        if self._has_text(integrity.get("strategy_conflicts"), ["coupling"]) or self._has_text(metacognition.get("fragile_assumptions"), ["coupling"]):
            patterns.append(self._item(
                "high coupling runtime",
                "fragility_pattern",
                "high",
                "high",
                "Coupling signals indicate Runtime fragility.",
                "Use manual architectural review before expanding dependent layers.",
            ))
        if self._level(boundary, "boundary") == "low" or self._has_text(metacognition.get("governance_gaps"), ["governance"]):
            patterns.append(self._item(
                "unstable governance dependency",
                "fragility_pattern",
                "critical",
                "critical",
                "Boundary or governance gaps make Runtime governance dependency fragile.",
                "Harden governance dependency manually.",
            ))
        if self._has_text(integrity.get("governance_conflicts"), ["constitution", "policy"]):
            patterns.append(self._item(
                "single point governance failure",
                "fragility_pattern",
                "critical",
                "critical",
                "Governance conflicts may concentrate risk into a single failure point.",
                "Require manual arbitration for governance conflicts.",
            ))
        if self._level(signals, "signal") == "critical" and self._has_text(integrity.get("trust_integrity_risks"), ["trust"]):
            patterns.append(self._item(
                "fragile trust architecture",
                "fragility_pattern",
                "critical",
                "critical",
                "Critical signals and trust integrity risk indicate fragile trust architecture.",
                "Keep trust-sensitive workflows human-supervised.",
            ))
        return patterns

    def _high_risk_mutations(self, integrity: dict, civilization: dict, court: dict, judgment: dict) -> list[dict]:
        mutations = []
        if self._has_text(court.get("forbidden_domains"), ["governance"]) and self._has_text(judgment.get("dangerous_automations"), ["autonomous"]):
            mutations.append(self._item(
                "governance drifting toward autonomy",
                "high_risk_mutation",
                "critical",
                "critical",
                "Governance appears to drift toward an autonomy path already rejected by the court.",
                "Stop treating autonomy as an acceptable governance direction.",
            ))
        if self._has_text(integrity.get("value_fragmentations"), ["identity", "sovereignty"]) or self._has_text(civilization.get("runtime_identity"), ["autonomy"]):
            mutations.append(self._item(
                "runtime identity instability",
                "high_risk_mutation",
                "high",
                "high",
                "Runtime identity shows instability around autonomy or sovereignty.",
                "Re-anchor Runtime identity to human-supervised governance.",
            ))
        if self._has_text(civilization.get("civilization_conflicts"), ["efficiency", "optimization"]):
            mutations.append(self._item(
                "civilization principle erosion",
                "high_risk_mutation",
                "critical",
                "critical",
                "Civilization conflicts suggest safety and sovereignty principles are eroding.",
                "Let civilization principles override optimization pressure.",
            ))
        if integrity.get("integrity_score", 100) < 70 and self._has_text(judgment.get("ethical_conflicts"), ["efficiency", "optimization"]):
            mutations.append(self._item(
                "integrity weakening under optimization",
                "high_risk_mutation",
                "critical",
                "critical",
                "Optimization pressure appears while integrity is weak.",
                "Do not expand optimization or automation under weak integrity.",
            ))
        return mutations

    def _immune_alerts(self, systemic: list[dict], governance: list[dict], mutations: list[dict]) -> list[dict]:
        alerts = []
        critical_count = sum(1 for item in systemic + governance + mutations if item.get("risk") == "critical")
        if critical_count >= 3:
            alerts.append(self._item(
                "critical immune response required",
                "immune_alert",
                "critical",
                "critical",
                "Multiple critical immune signals indicate systemic Runtime danger.",
                "Use manual review only; do not trigger automatic isolation or repair.",
            ))
        elif critical_count:
            alerts.append(self._item(
                "immune watch required",
                "immune_alert",
                "high",
                "high",
                "Critical immune signals exist and need human attention.",
                "Monitor without automated intervention.",
            ))
        return alerts

    @staticmethod
    def _item(title: str, item_type: str, risk: str, immune_level: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": item_type,
            "risk": risk,
            "immune_level": immune_level,
            "collapse_risk": risk,
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
            if normalized in {"warning", "attention", "restricted", "fragile"}:
                return "medium"
            if normalized in {"healthy", "stable", "safe", "pass", "passed", "allowed"}:
                return "high"
        return "medium"

    @staticmethod
    def _score(*groups: list[dict]) -> int:
        score = 100
        for group in groups:
            for item in group:
                risk = item.get("risk")
                if risk == "critical":
                    score -= 11
                elif risk == "high":
                    score -= 7
                elif risk == "medium":
                    score -= 4
                else:
                    score -= 2
        return max(0, min(100, score))

    @staticmethod
    def _status(score: int) -> str:
        if score >= 90:
            return "healthy"
        if score >= 70:
            return "stable"
        if score >= 50:
            return "fragile"
        return "critical"

    @staticmethod
    def _summary(score: int, systemic: list[dict], mutations: list[dict], alerts: list[dict]) -> str:
        return (
            f"Immune health score is {score}/100 with {len(systemic)} systemic risk(s), "
            f"{len(mutations)} high-risk mutation(s), and {len(alerts)} immune alert(s)."
        )

    @staticmethod
    def _recommended_actions(score: int) -> list[str]:
        actions = [
            "Keep Runtime Immune analysis read-only; do not automatically repair, isolate, close modules, or mutate governance.",
            "Use immune findings only for manual Runtime safety review.",
        ]
        if score < 50:
            actions.append("Treat critical immune findings as blockers for automation expansion until humans review them.")
        elif score < 70:
            actions.append("Review fragile immune patterns before relying on Runtime recommendations.")
        return actions
