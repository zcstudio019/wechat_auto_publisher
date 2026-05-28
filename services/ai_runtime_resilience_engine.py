"""Read-only resilience analysis for AI Runtime OS."""


class AIRuntimeResilienceEngine:
    """Assess Runtime resilience without recovering, repairing, or restructuring."""

    def build_resilience_analysis(
        self,
        immune_center,
        adaptive_center,
        integrity_center,
        civilization_center,
        forecast_center,
        intervention_center,
        simulation_center,
        memory_center,
    ) -> dict:
        immune_center = immune_center or {}
        adaptive_center = adaptive_center or {}
        integrity_center = integrity_center or {}
        civilization_center = civilization_center or {}
        forecast_center = forecast_center or {}
        intervention_center = intervention_center or {}
        simulation_center = simulation_center or {}
        memory_center = memory_center or {}

        recovery_capabilities = self._recovery_capabilities(intervention_center, simulation_center, memory_center)
        fragility_patterns = self._fragility_patterns(immune_center, adaptive_center, integrity_center)
        robustness_patterns = self._robustness_patterns(civilization_center, intervention_center, simulation_center)
        resilience_patterns = self._resilience_patterns(memory_center, intervention_center, forecast_center)
        antifragile_patterns = self._antifragile_patterns(memory_center, civilization_center, integrity_center)
        collapse_risks = self._collapse_risks(immune_center, adaptive_center, integrity_center)
        irreversible_failure_risks = self._irreversible_failure_risks(civilization_center, immune_center, integrity_center)
        stress_response_patterns = self._stress_response_patterns(adaptive_center, immune_center, simulation_center)
        resilience_score = self._score(
            recovery_capabilities,
            robustness_patterns,
            resilience_patterns,
            antifragile_patterns,
            fragility_patterns,
            collapse_risks,
            irreversible_failure_risks,
            stress_response_patterns,
        )

        return {
            "resilience_status": self._status(resilience_score),
            "resilience_score": resilience_score,
            "recovery_capabilities": recovery_capabilities,
            "fragility_patterns": fragility_patterns,
            "robustness_patterns": robustness_patterns,
            "resilience_patterns": resilience_patterns,
            "antifragile_patterns": antifragile_patterns,
            "collapse_risks": collapse_risks,
            "irreversible_failure_risks": irreversible_failure_risks,
            "stress_response_patterns": stress_response_patterns,
            "long_term_resilience_outlook": self._outlook(resilience_score, fragility_patterns, collapse_risks, antifragile_patterns),
            "recommended_actions": self._recommended_actions(resilience_score),
        }

    def _recovery_capabilities(self, intervention: dict, simulation: dict, memory: dict) -> list[dict]:
        items = []
        if intervention.get("manual_review_interventions") or self._has_text(memory.get("governance_lessons"), ["governance"]):
            items.append(self._item(
                "governance recovery",
                "recovery_capability",
                "resilient",
                "low",
                "Manual governance review provides a recovery path after governance shocks.",
                "Keep governance recovery manual and auditable.",
            ))
        if self._has_text(memory.get("organizational_wisdom"), ["trust"]) or self._has_text(simulation.get("best_case_scenarios"), ["trust"]):
            items.append(self._item(
                "trust recovery",
                "recovery_capability",
                "resilient",
                "low",
                "Trust lessons or best-case simulations indicate a possible trust recovery path.",
                "Use trust recovery as a validation target, not an automatic action.",
            ))
        if simulation.get("rollback_impacts") or self._has_text(intervention.get("post_checks"), ["rollback", "release"]):
            items.append(self._item(
                "rollback recovery",
                "recovery_capability",
                "robust",
                "medium",
                "Rollback impacts or post-checks indicate recovery options after failed changes.",
                "Verify rollback manually before any release-sensitive workflow.",
            ))
        if self._has_text(intervention.get("blocking_interventions"), ["freeze", "isolation", "block"]):
            items.append(self._item(
                "bounded isolation recovery",
                "recovery_capability",
                "robust",
                "medium",
                "Blocking recommendations provide bounded containment without automatic isolation.",
                "Keep containment as a recommendation only.",
            ))
        return items

    def _fragility_patterns(self, immune: dict, adaptive: dict, integrity: dict) -> list[dict]:
        patterns = []
        if self._has_text(immune.get("fragility_patterns"), ["governance"]) or self._has_text(integrity.get("governance_conflicts"), ["governance"]):
            patterns.append(self._item(
                "single governance dependency",
                "fragility_pattern",
                "fragile",
                "critical",
                "Governance risk concentrates recovery around a single dependency.",
                "Reduce governance single points of failure through manual architecture review.",
            ))
        if self._has_text(immune.get("fragility_patterns"), ["coupling", "runtime"]) or self._has_text(adaptive.get("environment_change_signals"), ["complexity"]):
            patterns.append(self._item(
                "over-centralized runtime",
                "fragility_pattern",
                "fragile",
                "high",
                "Runtime coupling and complexity reduce shock absorption.",
                "Prefer modular Runtime boundaries before expansion.",
            ))
        if immune.get("trust_decay_patterns") or self._has_text(adaptive.get("evolutionary_pressures"), ["trust"]):
            patterns.append(self._item(
                "trust-sensitive scaling",
                "fragility_pattern",
                "fragile",
                "critical",
                "Scaling depends on unstable trust conditions.",
                "Gate scaling on trust recovery and manual review.",
            ))
        if immune.get("dangerous_automation_patterns") or self._has_text(adaptive.get("environment_change_signals"), ["automation"]):
            patterns.append(self._item(
                "unstable automation expansion",
                "fragility_pattern",
                "fragile",
                "critical",
                "Automation pressure can amplify shocks instead of absorbing them.",
                "Keep automation bounded and observational.",
            ))
        return patterns

    def _robustness_patterns(self, civilization: dict, intervention: dict, simulation: dict) -> list[dict]:
        patterns = []
        if civilization.get("human_first_principles") or self._has_text(intervention.get("never_auto_interventions"), ["automatic", "auto"]):
            patterns.append(self._item(
                "bounded automation",
                "robustness_pattern",
                "robust",
                "low",
                "Human-first principles and never-auto rules make automation boundaries more robust.",
                "Preserve never-auto boundaries.",
            ))
        if civilization.get("governance_philosophies") or self._has_text(intervention.get("manual_review_interventions"), ["governance"]):
            patterns.append(self._item(
                "stable governance structure",
                "robustness_pattern",
                "robust",
                "low",
                "Governance philosophy and manual review create structure under stress.",
                "Keep governance structure visible in decision review.",
            ))
        if self._has_text(simulation.get("best_case_scenarios"), ["trust"]) or self._has_text(civilization.get("core_values"), ["trust"]):
            patterns.append(self._item(
                "resilient trust architecture",
                "robustness_pattern",
                "robust",
                "medium",
                "Trust is represented as a value or recovery target.",
                "Validate trust recovery through post-checks.",
            ))
        return patterns

    def _resilience_patterns(self, memory: dict, intervention: dict, forecast: dict) -> list[dict]:
        patterns = []
        if memory.get("stability_lessons") or memory.get("governance_lessons"):
            patterns.append(self._item(
                "system learns from failures",
                "resilience_pattern",
                "resilient",
                "low",
                "Memory contains lessons that can improve future response after failures.",
                "Use lessons in manual review and planning.",
            ))
        if self._has_text(memory.get("governance_lessons"), ["stabilize", "governance"]) and intervention.get("post_checks"):
            patterns.append(self._item(
                "governance stabilizes after shocks",
                "resilience_pattern",
                "resilient",
                "low",
                "Governance lessons plus post-checks indicate recovery discipline.",
                "Keep post-checks mandatory for governance-sensitive work.",
            ))
        if self._has_text(memory.get("organizational_wisdom"), ["trust"]) and not self._has_text(forecast.get("potential_risks"), ["trust collapse"]):
            patterns.append(self._item(
                "trust recovers after incidents",
                "resilience_pattern",
                "resilient",
                "medium",
                "Organizational wisdom includes trust recovery constraints.",
                "Use trust recovery as a manual readiness signal.",
            ))
        return patterns

    def _antifragile_patterns(self, memory: dict, civilization: dict, integrity: dict) -> list[dict]:
        patterns = []
        if self._has_text(memory.get("governance_lessons"), ["strengthen", "boundary", "governance"]):
            patterns.append(self._item(
                "shocks improve governance",
                "antifragile_pattern",
                "antifragile",
                "low",
                "Past governance lessons can make later governance stronger after shocks.",
                "Convert shock lessons into manual governance review criteria.",
            ))
        if self._has_text(memory.get("organizational_wisdom"), ["trust"]) and self._has_text(civilization.get("core_values"), ["trust"]):
            patterns.append(self._item(
                "incidents strengthen trust controls",
                "antifragile_pattern",
                "antifragile",
                "low",
                "Trust wisdom and civilization values can turn incidents into stronger trust controls.",
                "Keep trust controls explicit and human-reviewed.",
            ))
        if self._has_text(memory.get("stability_lessons"), ["architecture", "coupling", "fragility"]):
            patterns.append(self._item(
                "failures improve architecture",
                "antifragile_pattern",
                "antifragile",
                "medium",
                "Stability lessons identify architectural improvements after failures.",
                "Use architecture lessons without automatic restructuring.",
            ))
        if self._has_text(civilization.get("human_first_principles"), ["human", "approval"]) and self._has_text(integrity.get("consistency_checks"), ["boundary"]):
            patterns.append(self._item(
                "crises improve constitutional boundaries",
                "antifragile_pattern",
                "antifragile",
                "low",
                "Human-first principles and boundary consistency can strengthen constitutional limits after crises.",
                "Keep boundary strengthening manual.",
            ))
        return patterns

    def _collapse_risks(self, immune: dict, adaptive: dict, integrity: dict) -> list[dict]:
        risks = []
        if immune.get("systemic_risks") or immune.get("governance_corruption_risks"):
            risks.append(self._item(
                "cascading governance failure",
                "collapse_risk",
                "fragile",
                "critical",
                "Systemic or governance corruption risk can cascade through Runtime governance.",
                "Escalate to manual governance review before relying on recommendations.",
            ))
        if immune.get("trust_decay_patterns") or self._has_text(adaptive.get("long_term_survival_risks"), ["trust"]):
            risks.append(self._item(
                "trust collapse cascade",
                "collapse_risk",
                "fragile",
                "critical",
                "Trust decay can cascade into decisions, strategy, and automation readiness.",
                "Block automation expansion until trust is reviewed manually.",
            ))
        if integrity.get("integrity_score", 100) < 50 or self._has_text(immune.get("systemic_risks"), ["integrity"]):
            risks.append(self._item(
                "integrity collapse escalation",
                "collapse_risk",
                "fragile",
                "critical",
                "Low integrity can escalate into system-wide Runtime collapse.",
                "Treat integrity recovery as a manual prerequisite.",
            ))
        return risks

    def _irreversible_failure_risks(self, civilization: dict, immune: dict, integrity: dict) -> list[dict]:
        risks = []
        if self._has_text(civilization.get("civilization_conflicts"), ["constitution"]) or self._has_text(immune.get("high_risk_mutations"), ["principle erosion"]):
            risks.append(self._item(
                "constitutional erosion",
                "irreversible_failure_risk",
                "fragile",
                "critical",
                "Constitutional or principle erosion can become difficult to reverse.",
                "Keep constitution and civilization changes manual-only.",
            ))
        if self._has_text(immune.get("high_risk_mutations"), ["identity"]) or self._has_text(integrity.get("value_fragmentations"), ["sovereignty", "identity"]):
            risks.append(self._item(
                "civilization identity collapse",
                "irreversible_failure_risk",
                "fragile",
                "critical",
                "Identity instability can erode Runtime civilization over time.",
                "Re-anchor identity to human-supervised governance.",
            ))
        if self._has_text(immune.get("governance_corruption_risks"), ["governance"]) or self._has_text(integrity.get("governance_conflicts"), ["policy", "constitution"]):
            risks.append(self._item(
                "governance legitimacy loss",
                "irreversible_failure_risk",
                "fragile",
                "critical",
                "Governance conflicts can reduce legitimacy if unresolved.",
                "Resolve legitimacy conflicts through manual court and policy review.",
            ))
        return risks

    def _stress_response_patterns(self, adaptive: dict, immune: dict, simulation: dict) -> list[dict]:
        patterns = []
        if self._has_text(adaptive.get("aging_governance_patterns"), ["rigid", "slowing"]) or self._has_text(adaptive.get("civilization_rigidity_risks"), ["conservative"]):
            patterns.append(self._item(
                "governance freezes under stress",
                "stress_response_pattern",
                "fragile",
                "high",
                "Governance rigidity can freeze response during shocks.",
                "Clarify manual emergency review without automating authority.",
            ))
        if immune.get("dangerous_automation_patterns") or self._has_text(adaptive.get("environment_change_signals"), ["automation"]):
            patterns.append(self._item(
                "automation expands under pressure",
                "stress_response_pattern",
                "fragile",
                "critical",
                "Automation expansion under pressure can amplify failures.",
                "Keep automation expansion blocked until manual review.",
            ))
        if immune.get("trust_decay_patterns") or self._has_text(simulation.get("worst_case_scenarios"), ["trust"]):
            patterns.append(self._item(
                "trust weakens during scaling",
                "stress_response_pattern",
                "fragile",
                "critical",
                "Trust weakens under scaling or worst-case simulations.",
                "Use trust checks before scaling-sensitive recommendations.",
            ))
        return patterns

    @staticmethod
    def _item(title: str, item_type: str, resilience_level: str, risk: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": item_type,
            "resilience_level": resilience_level,
            "risk": risk,
            "summary": summary,
            "recommendation": recommendation,
        }

    @staticmethod
    def _has_text(items, needles: list[str]) -> bool:
        text = " ".join(str(item) for item in items or []).lower()
        return any(needle.lower() in text for needle in needles)

    @staticmethod
    def _score(
        recovery: list[dict],
        robustness: list[dict],
        resilience: list[dict],
        antifragile: list[dict],
        fragility: list[dict],
        collapse: list[dict],
        irreversible: list[dict],
        stress: list[dict],
    ) -> int:
        score = 62
        score += len(recovery) * 4
        score += len(robustness) * 5
        score += len(resilience) * 6
        score += len(antifragile) * 7
        for item in fragility + collapse + irreversible + stress:
            if item.get("risk") == "critical":
                score -= 10
            elif item.get("risk") == "high":
                score -= 7
            elif item.get("risk") == "medium":
                score -= 4
            else:
                score -= 2
        return max(0, min(100, score))

    @staticmethod
    def _status(score: int) -> str:
        if score >= 90:
            return "antifragile"
        if score >= 70:
            return "resilient"
        if score >= 50:
            return "fragile"
        return "critical"

    @staticmethod
    def _outlook(score: int, fragility: list[dict], collapse: list[dict], antifragile: list[dict]) -> str:
        return (
            f"Resilience score is {score}/100 with {len(fragility)} fragility pattern(s), "
            f"{len(collapse)} collapse risk(s), and {len(antifragile)} antifragile pattern(s)."
        )

    @staticmethod
    def _recommended_actions(score: int) -> list[str]:
        actions = [
            "Keep Runtime Resilience analysis read-only; do not automatically recover, repair, isolate, refactor, or upgrade.",
            "Use resilience findings for manual recovery planning and architecture review.",
        ]
        if score < 50:
            actions.append("Treat critical resilience findings as blockers for automation expansion until manually reviewed.")
        elif score < 70:
            actions.append("Review fragility and stress response before relying on Runtime recommendations.")
        return actions
