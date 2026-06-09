"""Read-only evolutionary fitness analysis for AI Runtime OS."""


class AIRuntimeEvolutionaryFitnessEngine:
    """Assess long-term Runtime fitness without淘汰, upgrading, or mutating state."""

    def build_fitness_analysis(
        self,
        adaptive_center,
        resilience_center,
        civilization_center,
        integrity_center,
        immune_center,
        strategy_center,
        governance_court_center,
        metacognition_center,
    ) -> dict:
        adaptive_center = adaptive_center or {}
        resilience_center = resilience_center or {}
        civilization_center = civilization_center or {}
        integrity_center = integrity_center or {}
        immune_center = immune_center or {}
        strategy_center = strategy_center or {}
        governance_court_center = governance_court_center or {}
        metacognition_center = metacognition_center or {}

        high_fitness_structures = self._high_fitness_structures(civilization_center, resilience_center, governance_court_center)
        low_fitness_structures = self._low_fitness_structures(adaptive_center, resilience_center, integrity_center, immune_center)
        survival_advantages = self._survival_advantages(resilience_center, civilization_center, governance_court_center)
        evolutionary_risks = self._evolutionary_risks(adaptive_center, immune_center, metacognition_center, strategy_center)
        obsolete_patterns = self._obsolete_patterns(adaptive_center, metacognition_center, strategy_center)
        long_term_adaptive_patterns = self._long_term_adaptive_patterns(adaptive_center, resilience_center, strategy_center)
        civilization_survival_patterns = self._civilization_survival_patterns(civilization_center, governance_court_center, integrity_center)
        extinction_risks = self._extinction_risks(civilization_center, immune_center, integrity_center, adaptive_center)
        selection_pressures = self._selection_pressures(adaptive_center, immune_center, strategy_center, resilience_center)
        fitness_score = self._score(
            high_fitness_structures,
            survival_advantages,
            long_term_adaptive_patterns,
            civilization_survival_patterns,
            low_fitness_structures,
            evolutionary_risks,
            obsolete_patterns,
            extinction_risks,
            selection_pressures,
        )

        return {
            "fitness_status": self._status(fitness_score),
            "fitness_score": fitness_score,
            "high_fitness_structures": high_fitness_structures,
            "low_fitness_structures": low_fitness_structures,
            "survival_advantages": survival_advantages,
            "evolutionary_risks": evolutionary_risks,
            "obsolete_patterns": obsolete_patterns,
            "long_term_adaptive_patterns": long_term_adaptive_patterns,
            "civilization_survival_patterns": civilization_survival_patterns,
            "extinction_risks": extinction_risks,
            "selection_pressures": selection_pressures,
            "evolutionary_summary": self._summary(fitness_score, high_fitness_structures, low_fitness_structures, extinction_risks, selection_pressures),
            "recommended_actions": self._recommended_actions(fitness_score),
        }

    def _high_fitness_structures(self, civilization: dict, resilience: dict, court: dict) -> list[dict]:
        structures = []
        if self._has_text(civilization.get("governance_philosophies"), ["bounded"]) or court.get("restricted_domains"):
            structures.append(self._item(
                "bounded governance",
                "high_fitness_structure",
                "high fitness",
                "low",
                "Bounded governance improves long-term survivability because it limits uncontrolled expansion.",
                "Preserve bounded governance as a long-term selection advantage.",
            ))
        if resilience.get("resilience_status") in {"resilient", "antifragile"} or resilience.get("robustness_patterns"):
            structures.append(self._item(
                "resilient civilization architecture",
                "high_fitness_structure",
                "high fitness",
                "low",
                "Resilience and robustness patterns increase long-term civilization survival capacity.",
                "Keep resilience and civilization principles connected.",
            ))
        if self._has_text(civilization.get("core_values"), ["trust"]) or self._has_text(resilience.get("recovery_capabilities"), ["trust"]):
            structures.append(self._item(
                "adaptive trust systems",
                "high_fitness_structure",
                "high fitness",
                "medium",
                "Trust-aware recovery and values improve adaptation under changing conditions.",
                "Use trust as a selection gate for scaling.",
            ))
        if court.get("governance_overrides") or self._has_text(civilization.get("human_first_principles"), ["human", "approval"]):
            structures.append(self._item(
                "layered constitutional protection",
                "high_fitness_structure",
                "high fitness",
                "low",
                "Layered court and human-first constraints protect Runtime from unsafe evolutionary drift.",
                "Keep constitutional protection above optimization pressure.",
            ))
        return structures

    def _low_fitness_structures(self, adaptive: dict, resilience: dict, integrity: dict, immune: dict) -> list[dict]:
        structures = []
        if self._has_text(resilience.get("fragility_patterns"), ["centralized", "runtime"]) or self._has_text(immune.get("fragility_patterns"), ["coupling"]):
            structures.append(self._item(
                "centralized fragile runtime",
                "low_fitness_structure",
                "low fitness",
                "critical",
                "Centralized fragile Runtime structures are likely to lose under long-term complexity pressure.",
                "Prefer modular Runtime structure through manual architecture review.",
            ))
        if self._has_text(resilience.get("fragility_patterns"), ["trust-sensitive"]) or self._has_text(integrity.get("strategy_conflicts"), ["trust"]):
            structures.append(self._item(
                "trust-dependent scaling",
                "low_fitness_structure",
                "low fitness",
                "critical",
                "Scaling that depends on unstable trust has poor evolutionary fitness.",
                "Gate scaling through trust and resilience checks.",
            ))
        if self._has_text(adaptive.get("aging_governance_patterns"), ["slowing", "rigid"]) or self._has_text(immune.get("governance_corruption_risks"), ["governance"]):
            structures.append(self._item(
                "governance bottleneck architecture",
                "low_fitness_structure",
                "low fitness",
                "high",
                "Governance bottlenecks reduce adaptation speed and long-term survivability.",
                "Simplify governance paths without automating authority.",
            ))
        return structures

    def _survival_advantages(self, resilience: dict, civilization: dict, court: dict) -> list[dict]:
        advantages = []
        if resilience.get("resilience_status") in {"resilient", "antifragile"} or resilience.get("recovery_capabilities"):
            advantages.append(self._item(
                "strong resilience adaptation",
                "survival_advantage",
                "high fitness",
                "low",
                "Recovery and resilience patterns provide a survival advantage after shocks.",
                "Keep recovery planning manual and auditable.",
            ))
        if civilization.get("human_first_principles") or court.get("constitutional_conflicts") is not None:
            advantages.append(self._item(
                "constitutional stability",
                "survival_advantage",
                "high fitness",
                "low",
                "Constitutional stability preserves Runtime identity across environmental change.",
                "Keep constitutional continuity as a long-term survival rule.",
            ))
        if self._has_text(civilization.get("forbidden_civilization_paths"), ["autonomous", "uncontrolled"]) or court.get("permanent_prohibitions"):
            advantages.append(self._item(
                "bounded automation survival advantage",
                "survival_advantage",
                "high fitness",
                "medium",
                "Bounded automation avoids civilization regression from uncontrolled optimization.",
                "Keep forbidden automation paths explicit.",
            ))
        return advantages

    def _evolutionary_risks(self, adaptive: dict, immune: dict, metacognition: dict, strategy: dict) -> list[dict]:
        risks = []
        if adaptive.get("civilization_rigidity_risks") or self._has_text(metacognition.get("strategic_biases"), ["rigid"]):
            risks.append(self._item(
                "governance rigidity",
                "evolutionary_risk",
                "unstable evolution",
                "high",
                "Governance rigidity may prevent necessary adaptation.",
                "Separate immutable values from adaptable procedures.",
            ))
        if self._has_text(metacognition.get("cognitive_conflicts"), ["strategy", "governance"]) or adaptive.get("cognitive_stagnation_patterns"):
            risks.append(self._item(
                "civilization stagnation",
                "evolutionary_risk",
                "unstable evolution",
                "high",
                "Cognitive stagnation can prevent civilization from adapting safely.",
                "Review repeated assumptions manually.",
            ))
        if adaptive.get("adaptive_status") == "critical" or adaptive.get("adaptation_score", 100) < 50:
            risks.append(self._item(
                "adaptation collapse",
                "evolutionary_risk",
                "extinction risk",
                "critical",
                "Low adaptation score indicates the current Runtime model may not fit future conditions.",
                "Treat adaptation collapse as a manual strategy review trigger.",
            ))
        if immune.get("dangerous_automation_patterns") or self._has_text(strategy.get("automation_roadmap"), ["automation", "scaling"]):
            risks.append(self._item(
                "over-automation fragility",
                "evolutionary_risk",
                "unstable evolution",
                "critical",
                "Over-automation creates fragile selection pressure against long-term civilization survival.",
                "Keep automation bounded and human-reviewed.",
            ))
        return risks

    def _obsolete_patterns(self, adaptive: dict, metacognition: dict, strategy: dict) -> list[dict]:
        patterns = []
        if adaptive.get("aging_governance_patterns") or self._has_text(metacognition.get("fragile_assumptions"), ["governance"]):
            patterns.append(self._item(
                "outdated governance assumptions",
                "obsolete_pattern",
                "low fitness",
                "high",
                "Old governance assumptions may no longer match Runtime complexity.",
                "Refresh governance assumptions through manual review.",
            ))
        if self._has_text(strategy.get("technical_debt_risks"), ["recovery", "coupling"]) or adaptive.get("long_term_survival_risks"):
            patterns.append(self._item(
                "brittle recovery logic",
                "obsolete_pattern",
                "low fitness",
                "high",
                "Recovery assumptions are brittle under long-term survival pressure.",
                "Strengthen recovery planning without automatic repair.",
            ))
        if self._has_text(strategy.get("technical_debt_risks"), ["central", "dashboard", "runtime"]):
            patterns.append(self._item(
                "centralized control dependency",
                "obsolete_pattern",
                "low fitness",
                "high",
                "Centralized dependencies are likely to be selected against under complexity.",
                "Prefer modular control boundaries.",
            ))
        return patterns

    def _long_term_adaptive_patterns(self, adaptive: dict, resilience: dict, strategy: dict) -> list[dict]:
        patterns = []
        if adaptive.get("required_adaptations") and not self._has_text(adaptive.get("required_adaptations"), ["automatic"]):
            patterns.append(self._item(
                "adaptive governance evolution",
                "long_term_adaptive_pattern",
                "high fitness",
                "medium",
                "Required adaptations make governance evolution visible without automatic mutation.",
                "Use required adaptations as manual roadmap inputs.",
            ))
        if resilience.get("robustness_patterns") or resilience.get("resilience_patterns"):
            patterns.append(self._item(
                "distributed resilience",
                "long_term_adaptive_pattern",
                "high fitness",
                "low",
                "Resilience distributed across recovery, robustness, and learning improves long-term fit.",
                "Keep resilience patterns distributed across layers.",
            ))
        if self._has_text(strategy.get("governance_roadmap"), ["boundary", "policy", "governance"]) or self._has_text(adaptive.get("required_adaptations"), ["bounded"]):
            patterns.append(self._item(
                "bounded strategic adaptation",
                "long_term_adaptive_pattern",
                "high fitness",
                "medium",
                "Strategy adapts best when bounded by governance and trust-aware constraints.",
                "Keep strategic adaptation bounded by court and civilization limits.",
            ))
        return patterns

    def _civilization_survival_patterns(self, civilization: dict, court: dict, integrity: dict) -> list[dict]:
        patterns = []
        if civilization.get("human_first_principles") or court.get("human_sovereignty_domains"):
            patterns.append(self._item(
                "human sovereignty preservation",
                "civilization_survival_pattern",
                "high fitness",
                "low",
                "Human sovereignty preserves legitimacy across long-term Runtime evolution.",
                "Keep human sovereignty non-optional.",
            ))
        if civilization.get("core_values") or court.get("governance_overrides"):
            patterns.append(self._item(
                "constitutional continuity",
                "civilization_survival_pattern",
                "high fitness",
                "low",
                "Core values and governance overrides protect continuity through change.",
                "Use constitutional continuity as the top-level fitness constraint.",
            ))
        if self._has_text(civilization.get("core_values"), ["trust"]) or self._has_text(integrity.get("trust_integrity_risks"), ["trust"]):
            patterns.append(self._item(
                "trust-preserving scaling",
                "civilization_survival_pattern",
                "high fitness",
                "medium",
                "Scaling has better survival odds when trust remains explicit.",
                "Make trust-preserving scaling a manual review criterion.",
            ))
        return patterns

    def _extinction_risks(self, civilization: dict, immune: dict, integrity: dict, adaptive: dict) -> list[dict]:
        risks = []
        if self._has_text(immune.get("high_risk_mutations"), ["identity", "legitimacy"]) or self._has_text(civilization.get("civilization_conflicts"), ["legitimacy"]):
            risks.append(self._item(
                "civilization legitimacy collapse",
                "extinction_risk",
                "extinction risk",
                "critical",
                "Civilization legitimacy collapse threatens long-term survival.",
                "Re-anchor legitimacy through human sovereignty and court constraints.",
            ))
        if immune.get("governance_corruption_risks") or self._has_text(integrity.get("governance_conflicts"), ["constitution", "policy"]):
            risks.append(self._item(
                "irreversible governance corruption",
                "extinction_risk",
                "extinction risk",
                "critical",
                "Governance corruption can become irreversible under long-term pressure.",
                "Treat governance corruption as a manual court-level blocker.",
            ))
        if adaptive.get("adaptive_status") == "critical" and immune.get("systemic_risks"):
            risks.append(self._item(
                "adaptive failure cascade",
                "extinction_risk",
                "extinction risk",
                "critical",
                "Critical adaptation failure plus systemic immune risk can cascade into extinction-level Runtime failure.",
                "Pause automation expansion and review future fit manually.",
            ))
        return risks

    def _selection_pressures(self, adaptive: dict, immune: dict, strategy: dict, resilience: dict) -> list[dict]:
        pressures = []
        if self._has_text(adaptive.get("evolutionary_pressures"), ["scaling"]) or self._has_text(strategy.get("automation_roadmap"), ["scaling"]):
            pressures.append(self._item("scaling pressure", "selection_pressure", "unstable evolution", "high", "Scaling pressure selects against fragile structures.", "Scale only after resilience and governance review."))
        if immune.get("trust_decay_patterns") or self._has_text(adaptive.get("evolutionary_pressures"), ["trust"]):
            pressures.append(self._item("trust pressure", "selection_pressure", "unstable evolution", "critical", "Trust pressure selects against confidence-only or delegation-heavy Runtime structures.", "Keep trust as a selection gate."))
        if immune.get("governance_corruption_risks") or self._has_text(adaptive.get("evolutionary_pressures"), ["governance"]):
            pressures.append(self._item("governance pressure", "selection_pressure", "unstable evolution", "critical", "Governance pressure selects against rigid or corruptible governance models.", "Simplify governance without automating authority."))
        if immune.get("dangerous_automation_patterns") or self._has_text(strategy.get("automation_roadmap"), ["automation"]):
            pressures.append(self._item("automation pressure", "selection_pressure", "unstable evolution", "critical", "Automation pressure selects against unbounded autonomy.", "Keep automation bounded and human-reviewed."))
        if self._has_text(adaptive.get("environment_change_signals"), ["complexity"]) or self._has_text(resilience.get("fragility_patterns"), ["centralized"]):
            pressures.append(self._item("complexity pressure", "selection_pressure", "unstable evolution", "high", "Complexity pressure selects against centralized fragile Runtime structure.", "Prefer modular Runtime boundaries."))
        return pressures

    @staticmethod
    def _item(title: str, item_type: str, fitness_level: str, risk: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": item_type,
            "fitness_level": fitness_level,
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
        high_structures: list[dict],
        advantages: list[dict],
        adaptive_patterns: list[dict],
        civilization_patterns: list[dict],
        low_structures: list[dict],
        evolutionary_risks: list[dict],
        obsolete_patterns: list[dict],
        extinction_risks: list[dict],
        pressures: list[dict],
    ) -> int:
        score = 58
        score += len(high_structures) * 5
        score += len(advantages) * 5
        score += len(adaptive_patterns) * 5
        score += len(civilization_patterns) * 6
        for item in low_structures + evolutionary_risks + obsolete_patterns + pressures:
            if item.get("risk") == "critical":
                score -= 9
            elif item.get("risk") == "high":
                score -= 6
            elif item.get("risk") == "medium":
                score -= 3
            else:
                score -= 1
        score -= len(extinction_risks) * 14
        return max(0, min(100, score))

    @staticmethod
    def _status(score: int) -> str:
        if score >= 90:
            return "evolutionary dominant"
        if score >= 70:
            return "high fitness"
        if score >= 50:
            return "unstable evolution"
        return "extinction risk"

    @staticmethod
    def _summary(score: int, high_structures: list[dict], low_structures: list[dict], extinction: list[dict], pressures: list[dict]) -> str:
        return (
            f"Evolutionary fitness score is {score}/100 with {len(high_structures)} high-fitness structure(s), "
            f"{len(low_structures)} low-fitness structure(s), {len(extinction)} extinction risk(s), "
            f"and {len(pressures)} selection pressure(s)."
        )

    @staticmethod
    def _recommended_actions(score: int) -> list[str]:
        actions = [
            "Keep Runtime Evolutionary Fitness analysis read-only; do not automatically淘汰, upgrade, refactor, replace modules, or mutate governance.",
            "Use fitness findings for manual long-term Runtime architecture and governance review.",
        ]
        if score < 50:
            actions.append("Treat extinction-risk findings as blockers for automation expansion until manually reviewed.")
        elif score < 70:
            actions.append("Review unstable evolutionary patterns before relying on long-term Runtime strategy.")
        return actions
