"""Read-only adaptive analysis for AI Runtime OS."""


class AIRuntimeAdaptiveEngine:
    """Assess long-term Runtime adaptability without upgrading or mutating state."""

    def build_adaptive_analysis(
        self,
        strategy_center,
        civilization_center,
        integrity_center,
        immune_center,
        metacognition_center,
        memory_center,
        forecast_center,
        signal_intelligence_center,
    ) -> dict:
        strategy_center = strategy_center or {}
        civilization_center = civilization_center or {}
        integrity_center = integrity_center or {}
        immune_center = immune_center or {}
        metacognition_center = metacognition_center or {}
        memory_center = memory_center or {}
        forecast_center = forecast_center or {}
        signal_intelligence_center = signal_intelligence_center or {}

        environment_change_signals = self._environment_change_signals(strategy_center, immune_center, forecast_center, signal_intelligence_center)
        aging_governance_patterns = self._aging_governance_patterns(civilization_center, metacognition_center, memory_center)
        strategic_obsolescence_risks = self._strategic_obsolescence_risks(strategy_center, integrity_center, immune_center)
        civilization_rigidity_risks = self._civilization_rigidity_risks(civilization_center, immune_center, metacognition_center)
        cognitive_stagnation_patterns = self._cognitive_stagnation_patterns(metacognition_center, memory_center, strategy_center)
        long_term_survival_risks = self._long_term_survival_risks(strategy_center, integrity_center, immune_center, forecast_center)
        required_adaptations = self._required_adaptations(
            aging_governance_patterns,
            strategic_obsolescence_risks,
            civilization_rigidity_risks,
            long_term_survival_risks,
        )
        evolutionary_pressures = self._evolutionary_pressures(
            environment_change_signals,
            strategic_obsolescence_risks,
            immune_center,
            signal_intelligence_center,
        )
        adaptation_score = self._score(
            environment_change_signals,
            aging_governance_patterns,
            strategic_obsolescence_risks,
            civilization_rigidity_risks,
            cognitive_stagnation_patterns,
            long_term_survival_risks,
            evolutionary_pressures,
        )

        return {
            "adaptive_status": self._status(adaptation_score),
            "adaptation_score": adaptation_score,
            "environment_change_signals": environment_change_signals,
            "aging_governance_patterns": aging_governance_patterns,
            "strategic_obsolescence_risks": strategic_obsolescence_risks,
            "civilization_rigidity_risks": civilization_rigidity_risks,
            "cognitive_stagnation_patterns": cognitive_stagnation_patterns,
            "long_term_survival_risks": long_term_survival_risks,
            "required_adaptations": required_adaptations,
            "evolutionary_pressures": evolutionary_pressures,
            "adaptive_summary": self._summary(adaptation_score, environment_change_signals, long_term_survival_risks, evolutionary_pressures),
            "recommended_actions": self._recommended_actions(adaptation_score),
        }

    def _environment_change_signals(self, strategy: dict, immune: dict, forecast: dict, signals: dict) -> list[dict]:
        items = []
        if self._has_text(strategy.get("technical_debt_risks"), ["coupling", "dashboard", "runtime"]) or immune.get("fragility_patterns"):
            items.append(self._item(
                "runtime complexity increasing",
                "environment_change_signal",
                "complexity pressure",
                "high",
                "Runtime complexity or coupling signals indicate the operating environment is becoming harder to govern.",
                "Increase modularity analysis before expanding Runtime layers.",
            ))
        if immune.get("governance_corruption_risks") or self._has_text(forecast.get("potential_risks"), ["governance"]):
            items.append(self._item(
                "governance pressure rising",
                "environment_change_signal",
                "governance pressure",
                "critical",
                "Governance risk is rising across immune or forecast signals.",
                "Keep governance review manual and simplify governance bottlenecks.",
            ))
        if immune.get("trust_decay_patterns") or self._level(signals, "signal") in {"low", "critical"}:
            items.append(self._item(
                "trust volatility increasing",
                "environment_change_signal",
                "trust pressure",
                "critical",
                "Trust decay or critical signal intelligence suggests trust volatility is increasing.",
                "Scale decisions by trust level rather than confidence alone.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["automation", "scaling"]) or immune.get("dangerous_automation_patterns"):
            items.append(self._item(
                "automation expansion accelerating",
                "environment_change_signal",
                "automation pressure",
                "high",
                "Automation ambitions are accelerating while Runtime still needs governance constraints.",
                "Keep automation bounded and non-self-expanding.",
            ))
        return items

    def _aging_governance_patterns(self, civilization: dict, metacognition: dict, memory: dict) -> list[dict]:
        items = []
        if self._has_text(metacognition.get("governance_gaps"), ["missing", "incomplete"]) or self._has_text(memory.get("governance_lessons"), ["outdated", "weak"]):
            items.append(self._item(
                "governance rules outdated",
                "aging_governance_pattern",
                "governance complexity pressure",
                "high",
                "Governance lessons and gaps suggest rules may no longer match Runtime complexity.",
                "Review governance rules manually before expanding scope.",
            ))
        if self._has_text(civilization.get("governance_philosophies"), ["slow", "conservative"]) and self._has_text(metacognition.get("strategic_biases"), ["postponed", "rigid"]):
            items.append(self._item(
                "policy structure too rigid",
                "aging_governance_pattern",
                "governance rigidity pressure",
                "high",
                "Governance philosophy may be too rigid for changing Runtime conditions.",
                "Keep safety first while simplifying policy paths.",
            ))
        if self._has_text(memory.get("organizational_wisdom"), ["manual", "approval"]) and self._has_text(metacognition.get("blind_spots"), ["human review"]):
            items.append(self._item(
                "approval flow slowing adaptation",
                "aging_governance_pattern",
                "review pressure",
                "medium",
                "Manual review remains necessary but may slow long-term adaptation if visibility is weak.",
                "Improve review visibility without automating approval.",
            ))
        return items

    def _strategic_obsolescence_risks(self, strategy: dict, integrity: dict, immune: dict) -> list[dict]:
        items = []
        if self._has_text(integrity.get("strategy_conflicts"), ["trust"]) or self._has_text(immune.get("trust_decay_patterns"), ["trust"]):
            items.append(self._item(
                "roadmap incompatible with trust level",
                "strategic_obsolescence_risk",
                "trust pressure",
                "critical",
                "Strategy appears incompatible with current trust and trust-decay signals.",
                "Reframe roadmap around trust-aware scaling.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["scaling"]) and immune.get("fragility_patterns"):
            items.append(self._item(
                "scaling strategy outdated",
                "strategic_obsolescence_risk",
                "scaling pressure",
                "high",
                "Scaling strategy may be outdated because Runtime fragility is already visible.",
                "Prioritize stability before scaling.",
            ))
        if immune.get("governance_corruption_risks") or self._has_text(strategy.get("technical_debt_risks"), ["governance"]):
            items.append(self._item(
                "governance model cannot scale",
                "strategic_obsolescence_risk",
                "governance complexity pressure",
                "critical",
                "Governance corruption or debt suggests the current governance model may not scale.",
                "Simplify governance model before adding autonomy.",
            ))
        return items

    def _civilization_rigidity_risks(self, civilization: dict, immune: dict, metacognition: dict) -> list[dict]:
        items = []
        if self._has_text(metacognition.get("strategic_biases"), ["conservative", "postponed"]) and civilization.get("forbidden_civilization_paths"):
            items.append(self._item(
                "civilization resisting necessary evolution",
                "civilization_rigidity_risk",
                "civilization pressure",
                "medium",
                "Civilization prohibitions are necessary, but they may need clearer adaptation channels.",
                "Clarify safe adaptation paths without weakening prohibitions.",
            ))
        if self._has_text(civilization.get("governance_philosophies"), ["slow", "bounded"]) and immune.get("systemic_risks"):
            items.append(self._item(
                "governance too conservative",
                "civilization_rigidity_risk",
                "governance pressure",
                "medium",
                "Slow governance protects safety but may become too conservative under systemic risk.",
                "Improve governance responsiveness while keeping human sovereignty.",
            ))
        if self._has_text(metacognition.get("governance_gaps"), ["blocked", "missing"]) and civilization.get("civilization_conflicts"):
            items.append(self._item(
                "adaptation blocked by rigidity",
                "civilization_rigidity_risk",
                "civilization pressure",
                "high",
                "Civilization conflict plus governance gaps may block needed adaptation.",
                "Separate immutable principles from adaptable procedures.",
            ))
        return items

    def _cognitive_stagnation_patterns(self, metacognition: dict, memory: dict, strategy: dict) -> list[dict]:
        items = []
        if self._has_text(metacognition.get("fragile_assumptions"), ["governance", "assumed"]) or self._has_text(memory.get("governance_lessons"), ["governance"]):
            items.append(self._item(
                "repeated governance assumptions",
                "cognitive_stagnation_pattern",
                "cognitive pressure",
                "high",
                "Governance assumptions are recurring across memory and metacognition.",
                "Re-evaluate assumptions manually instead of copying old reasoning.",
            ))
        if self._has_text(strategy.get("long_term_strategies"), ["stability", "governance"]) and self._has_text(memory.get("strategic_lessons"), ["stability before automation"]):
            items.append(self._item(
                "repetitive strategic thinking",
                "cognitive_stagnation_pattern",
                "strategy pressure",
                "medium",
                "Strategy repeats known lessons but may not generate new adaptation options.",
                "Add future-fit review to strategic planning.",
            ))
        if self._has_text(memory.get("repeated_patterns"), ["recurring", "loop", "storm"]) and not strategy.get("capability_priorities"):
            items.append(self._item(
                "memory loops without evolution",
                "cognitive_stagnation_pattern",
                "memory pressure",
                "high",
                "Memory records repeated patterns without clear capability evolution.",
                "Convert repeated patterns into explicit capability priorities.",
            ))
        return items

    def _long_term_survival_risks(self, strategy: dict, integrity: dict, immune: dict, forecast: dict) -> list[dict]:
        items = []
        if immune.get("immune_status") in {"critical", "fragile"} or immune.get("immune_health_score", 100) < 70:
            items.append(self._item(
                "system too fragile for future scaling",
                "long_term_survival_risk",
                "stability pressure",
                "critical",
                "Immune health indicates Runtime may be too fragile for future scaling.",
                "Treat stability as the primary adaptation priority.",
            ))
        if self._has_text(immune.get("governance_corruption_risks"), ["governance"]) or self._has_text(forecast.get("potential_risks"), ["governance"]):
            items.append(self._item(
                "governance cannot survive complexity",
                "long_term_survival_risk",
                "governance complexity pressure",
                "critical",
                "Governance risks may not survive increasing complexity.",
                "Simplify governance and keep court constraints visible.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["automation"]) and integrity.get("integrity_score", 100) < 70:
            items.append(self._item(
                "automation growth exceeds adaptation",
                "long_term_survival_risk",
                "automation pressure",
                "critical",
                "Automation growth appears to exceed current integrity and adaptation capacity.",
                "Delay automation expansion until integrity improves.",
            ))
        return items

    def _required_adaptations(self, governance: list[dict], strategy: list[dict], rigidity: list[dict], survival: list[dict]) -> list[dict]:
        items = []
        if governance:
            items.append(self._item(
                "governance simplification",
                "required_adaptation",
                "governance complexity pressure",
                "high",
                "Governance aging patterns require simpler, clearer review paths.",
                "Simplify governance manually without weakening constitution or policy gates.",
            ))
        if survival or strategy:
            items.append(self._item(
                "modular runtime structure",
                "required_adaptation",
                "stability pressure",
                "high",
                "Long-term survival and strategy risks require lower coupling.",
                "Use modular architecture review before further Runtime growth.",
            ))
        if strategy:
            items.append(self._item(
                "bounded automation redesign",
                "required_adaptation",
                "automation pressure",
                "critical",
                "Automation roadmap needs bounded redesign under trust and governance constraints.",
                "Keep automation observational or reporting-only until manual approval.",
            ))
        if rigidity or survival:
            items.append(self._item(
                "trust-aware scaling",
                "required_adaptation",
                "trust pressure",
                "critical",
                "Scaling should be conditioned on trust, integrity, and immune health.",
                "Require trust-aware scaling gates.",
            ))
        return items

    def _evolutionary_pressures(self, environment: list[dict], strategy: list[dict], immune: dict, signals: dict) -> list[dict]:
        pressures = []
        if self._has_text(environment + strategy, ["scaling", "automation"]):
            pressures.append(self._item("scaling pressure", "evolutionary_pressure", "scaling pressure", "high", "Runtime growth pressure is visible.", "Scale only after stability and governance review."))
        if self._has_text(environment + strategy, ["governance"]):
            pressures.append(self._item("governance complexity pressure", "evolutionary_pressure", "governance complexity pressure", "critical", "Governance complexity is becoming an adaptation constraint.", "Simplify governance paths without automating authority."))
        if immune.get("trust_decay_patterns") or self._level(signals, "signal") in {"low", "critical"}:
            pressures.append(self._item("trust pressure", "evolutionary_pressure", "trust pressure", "critical", "Trust volatility pressures future Runtime fit.", "Use trust-aware gates for any future roadmap."))
        if immune.get("fragility_patterns") or self._level(signals, "signal") == "medium":
            pressures.append(self._item("stability pressure", "evolutionary_pressure", "stability pressure", "high", "Runtime fragility increases stability pressure.", "Prioritize stability before autonomy."))
        if immune.get("civilization_regression_risks"):
            pressures.append(self._item("civilization pressure", "evolutionary_pressure", "civilization pressure", "high", "Civilization regression creates pressure to clarify principles.", "Clarify adaptable procedures while preserving immutable values."))
        return pressures

    @staticmethod
    def _item(title: str, item_type: str, pressure: str, risk: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": item_type,
            "evolutionary_pressure": pressure,
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
                    score -= 10
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
            return "highly_adaptive"
        if score >= 70:
            return "adaptive"
        if score >= 50:
            return "rigid"
        return "critical"

    @staticmethod
    def _summary(score: int, environment: list[dict], survival: list[dict], pressures: list[dict]) -> str:
        return (
            f"Adaptation score is {score}/100 with {len(environment)} environment change signal(s), "
            f"{len(survival)} long-term survival risk(s), and {len(pressures)} evolutionary pressure(s)."
        )

    @staticmethod
    def _recommended_actions(score: int) -> list[str]:
        actions = [
            "Keep Runtime Adaptive analysis read-only; do not automatically adapt, upgrade, refactor, or mutate governance.",
            "Use adaptive findings for manual long-term Runtime design review.",
        ]
        if score < 50:
            actions.append("Treat critical adaptation findings as blockers for automation expansion until manually reviewed.")
        elif score < 70:
            actions.append("Review rigidity and long-term fit before relying on future Runtime strategy.")
        return actions
