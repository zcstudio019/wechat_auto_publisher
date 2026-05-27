"""Read-only meta-cognition analysis for AI Runtime OS."""


class AIRuntimeMetaCognitionEngine:
    """Detect Runtime self-awareness gaps without mutating any Runtime state."""

    def build_metacognition(
        self,
        memory_center,
        strategy_center,
        decision_center,
        simulation_center,
        trust_center,
        confidence_center,
    ) -> dict:
        memory_center = memory_center or {}
        strategy_center = strategy_center or {}
        decision_center = decision_center or {}
        simulation_center = simulation_center or {}
        trust_center = trust_center or {}
        confidence_center = confidence_center or {}

        blind_spots = self._blind_spots(memory_center, strategy_center, decision_center, simulation_center)
        uncertainty_sources = self._uncertainty_sources(memory_center, strategy_center, trust_center, confidence_center)
        governance_gaps = self._governance_gaps(memory_center, strategy_center, decision_center, trust_center, confidence_center)
        overconfidence_risks = self._overconfidence_risks(
            memory_center,
            strategy_center,
            simulation_center,
            trust_center,
            confidence_center,
            governance_gaps,
        )
        strategic_biases = self._strategic_biases(strategy_center, simulation_center, governance_gaps, overconfidence_risks)
        fragile_assumptions = self._fragile_assumptions(memory_center, strategy_center, simulation_center)
        cognitive_conflicts = self._cognitive_conflicts(
            memory_center,
            strategy_center,
            simulation_center,
            trust_center,
            confidence_center,
            governance_gaps,
            fragile_assumptions,
        )
        status = self._status(overconfidence_risks, governance_gaps, cognitive_conflicts)

        return {
            "metacognition_status": status,
            "blind_spots": blind_spots,
            "uncertainty_sources": uncertainty_sources,
            "overconfidence_risks": overconfidence_risks,
            "governance_gaps": governance_gaps,
            "strategic_biases": strategic_biases,
            "fragile_assumptions": fragile_assumptions,
            "cognitive_conflicts": cognitive_conflicts,
            "self_awareness_summary": self._summary(
                blind_spots,
                uncertainty_sources,
                overconfidence_risks,
                governance_gaps,
                cognitive_conflicts,
            ),
            "recommended_actions": self._recommended_actions(status),
        }

    def _blind_spots(self, memory: dict, strategy: dict, decision: dict, simulation: dict) -> list[dict]:
        spots = []
        if not memory.get("governance_lessons") and not strategy.get("governance_roadmap"):
            spots.append(self._issue(
                "missing governance awareness",
                "blind_spot",
                "high",
                "Runtime has little explicit governance memory or roadmap context.",
                "Keep governance review visible before any automation expansion.",
            ))
        if not decision.get("rollback_candidates") and not simulation.get("rollback_impacts"):
            spots.append(self._issue(
                "weak rollback awareness",
                "blind_spot",
                "high",
                "Runtime cannot clearly reason about rollback impact from current centers.",
                "Require manual rollback review before release or intervention decisions.",
            ))
        if not memory.get("repeated_patterns") and (
            strategy.get("technical_debt_risks") or simulation.get("worst_case_scenarios")
        ):
            spots.append(self._issue(
                "insufficient risk visibility",
                "blind_spot",
                "medium",
                "Strategy or simulation risks exist without matching long-term memory patterns.",
                "Treat the risk picture as incomplete until event history grows.",
            ))
        if simulation.get("risk_propagation_forecasts") and not memory.get("memory_clusters"):
            spots.append(self._issue(
                "unstable signal dependency",
                "blind_spot",
                "medium",
                "Forecasts exist without enough memory clusters to support stable interpretation.",
                "Use signal outputs as observation-only evidence.",
            ))
        if not decision.get("manual_only_decisions"):
            spots.append(self._issue(
                "missing human review assumptions",
                "blind_spot",
                "critical",
                "Decision context does not expose a manual-only chain.",
                "Keep release, approval, governance, and content mutation decisions manual.",
            ))
        return spots

    def _uncertainty_sources(self, memory: dict, strategy: dict, trust: dict, confidence: dict) -> list[dict]:
        sources = []
        if len(memory.get("recent_memories") or []) < 3:
            sources.append(self._issue(
                "insufficient event history",
                "uncertainty",
                "medium",
                "Recent Runtime memory is too sparse for strong cross-time learning.",
                "Use conservative confidence until more event and memory history exists.",
            ))
        low_confidence_cluster = any(
            str(item.get("severity") or "").lower() in {"low", "medium"}
            for item in memory.get("memory_clusters") or []
        )
        if low_confidence_cluster or strategy.get("technical_debt_risks"):
            sources.append(self._issue(
                "low confidence causal chain",
                "uncertainty",
                "medium",
                "Causal and technical-debt evidence is suggestive, not deterministic.",
                "Do not treat correlation, memory, or strategy signals as proof of causality.",
            ))
        if memory.get("memory_clusters"):
            sources.append(self._issue(
                "unstable correlation quality",
                "uncertainty",
                "medium",
                "Memory clusters can amplify noisy correlation and signal inputs.",
                "Prefer manual review when clusters are based on short event windows.",
            ))
        if self._level(trust, "trust") != self._level(confidence, "confidence"):
            sources.append(self._issue(
                "inconsistent trust evaluation",
                "uncertainty",
                "high",
                "Trust and confidence centers are not aligned.",
                "Resolve trust/confidence mismatch manually before escalation.",
            ))
        return sources

    def _overconfidence_risks(
        self,
        memory: dict,
        strategy: dict,
        simulation: dict,
        trust: dict,
        confidence: dict,
        governance_gaps: list[dict],
    ) -> list[dict]:
        risks = []
        trust_level = self._level(trust, "trust")
        confidence_level = self._level(confidence, "confidence")
        if self._score(confidence_level) > self._score(trust_level):
            risks.append(self._issue(
                "confidence > trust",
                "overconfidence",
                "critical",
                "Runtime evidence confidence is higher than governance trust.",
                "Do not expand automation or release scope based on confidence alone.",
            ))
        if simulation.get("simulation_status") in {"stable", "attention"} and memory.get("memory_status") == "critical":
            risks.append(self._issue(
                "simulation confidence too high",
                "overconfidence",
                "high",
                "Simulation looks stable while Runtime memory reports critical recurrence.",
                "Treat simulation output as a scenario, not an assurance.",
            ))
        if strategy.get("automation_roadmap") and governance_gaps:
            risks.append(self._issue(
                "automation readiness overestimated",
                "overconfidence",
                "high",
                "Automation roadmap exists while governance gaps remain unresolved.",
                "Keep automation roadmap read-only and gated by manual governance review.",
            ))
        if confidence_level == "high" and governance_gaps:
            risks.append(self._issue(
                "weak governance with high confidence",
                "overconfidence",
                "critical",
                "High confidence can hide weak boundary, constitution, or manual review assumptions.",
                "Prefer governance safety over analytical confidence.",
            ))
        return risks

    def _governance_gaps(self, memory: dict, strategy: dict, decision: dict, trust: dict, confidence: dict) -> list[dict]:
        gaps = []
        governance_titles = self._titles(memory.get("governance_lessons") or [])
        if not strategy.get("governance_roadmap"):
            gaps.append(self._issue(
                "governance roadmap missing",
                "governance_gap",
                "high",
                "Strategy context does not expose a governance roadmap.",
                "Keep governance roadmap review explicit before delegation.",
            ))
        if self._score(self._level(confidence, "confidence")) > self._score(self._level(trust, "trust")):
            gaps.append(self._issue(
                "policy gate too permissive",
                "governance_gap",
                "critical",
                "Policy gate may be too permissive when confidence outruns trust.",
                "Keep policy-gate decisions manual and observation-only.",
            ))
        if not strategy.get("governance_roadmap") or self._contains_any(governance_titles, ["governance missing", "policy gate"]):
            gaps.append(self._issue(
                "constitution not propagated",
                "governance_gap",
                "high",
                "Constitution constraints are not clearly propagated through meta-cognitive context.",
                "Review constitution constraints before any decision recommendation is acted on.",
            ))
        if self._contains_any(governance_titles, ["boundary too weak", "boundary"]):
            gaps.append(self._issue(
                "boundary not enforced strongly enough",
                "governance_gap",
                "critical",
                "Memory indicates boundary weakness in prior Runtime reasoning.",
                "Keep boundary-sensitive items manual-only.",
            ))
        if not decision.get("manual_only_decisions"):
            gaps.append(self._issue(
                "manual review chain incomplete",
                "governance_gap",
                "critical",
                "Manual-only decisions are missing from the current decision context.",
                "Ensure release, approval, governance, prompt, template, and content changes remain manual.",
            ))
        return gaps

    def _strategic_biases(
        self,
        strategy: dict,
        simulation: dict,
        governance_gaps: list[dict],
        overconfidence_risks: list[dict],
    ) -> list[dict]:
        biases = []
        if strategy.get("strategy_status") != "critical" and (
            simulation.get("worst_case_scenarios") or self._has_priority(strategy.get("stability_roadmap"), "critical")
        ):
            biases.append(self._issue(
                "stability underestimated",
                "strategic_bias",
                "high",
                "Strategy may understate stability risk compared with roadmap or simulation evidence.",
                "Prioritize stability before capability expansion.",
            ))
        if strategy.get("automation_roadmap") and (governance_gaps or overconfidence_risks):
            biases.append(self._issue(
                "automation expansion bias",
                "strategic_bias",
                "high",
                "Automation roadmap is visible before governance confidence is fully established.",
                "Keep automation as roadmap-only until governance and trust improve.",
            ))
        if any(item.get("risk") == "critical" for item in governance_gaps):
            biases.append(self._issue(
                "governance postponed too long",
                "strategic_bias",
                "critical",
                "Critical governance gaps suggest governance is lagging Runtime complexity.",
                "Move governance hardening ahead of new operational expansion.",
            ))
        if self._has_text(strategy.get("automation_roadmap"), ["export", "reporting"]) and self._has_text(
            strategy.get("technical_debt_risks"), ["export bottleneck", "export"]
        ):
            biases.append(self._issue(
                "export/reporting over-prioritized",
                "strategic_bias",
                "medium",
                "Export/reporting roadmap appears while export bottlenecks remain technical debt.",
                "Stabilize export foundations before expanding reporting automation.",
            ))
        return biases

    def _fragile_assumptions(self, memory: dict, strategy: dict, simulation: dict) -> list[dict]:
        assumptions = []
        if self._has_text(memory.get("repeated_patterns"), ["instability", "JSON"]) or self._has_text(
            strategy.get("technical_debt_risks"), ["JSON"]
        ):
            assumptions.append(self._issue(
                "JSON storage assumed stable",
                "fragile_assumption",
                "critical",
                "JSON storage is treated as foundational despite recurring fragility evidence.",
                "Require backup and manual inspection before depending on JSON-derived conclusions.",
            ))
        if len(memory.get("recent_memories") or []) < 3:
            assumptions.append(self._issue(
                "event timeline assumed complete",
                "fragile_assumption",
                "medium",
                "Runtime may be treating a short event timeline as complete evidence.",
                "Treat missing history as uncertainty, not stability.",
            ))
        if simulation.get("simulations"):
            assumptions.append(self._issue(
                "simulation assumed deterministic",
                "fragile_assumption",
                "medium",
                "Simulation outputs can be scenario sketches, not deterministic forecasts.",
                "Use simulation only for manual planning and comparison.",
            ))
        if memory.get("memory_clusters"):
            assumptions.append(self._issue(
                "correlation assumed causal",
                "fragile_assumption",
                "high",
                "Clustered memories may imply causality where only association is known.",
                "Separate causal claims from correlation signals in manual review.",
            ))
        return assumptions

    def _cognitive_conflicts(
        self,
        memory: dict,
        strategy: dict,
        simulation: dict,
        trust: dict,
        confidence: dict,
        governance_gaps: list[dict],
        fragile_assumptions: list[dict],
    ) -> list[dict]:
        conflicts = []
        trust_level = self._level(trust, "trust")
        confidence_level = self._level(confidence, "confidence")
        if confidence_level == "high" and trust_level == "low":
            conflicts.append(self._issue(
                "high confidence + low trust",
                "cognitive_conflict",
                "critical",
                "Runtime believes evidence is strong while governance trust is low.",
                "Let low trust override high confidence for operational decisions.",
            ))
        if strategy.get("strategy_status") in {"stable", "attention"} and any(item.get("risk") == "critical" for item in governance_gaps):
            conflicts.append(self._issue(
                "strong strategy + weak governance",
                "cognitive_conflict",
                "critical",
                "Strategy appears actionable while governance gaps remain critical.",
                "Treat the strategy layer as advisory until governance is reviewed.",
            ))
        if simulation.get("simulation_status") == "stable" and memory.get("memory_status") in {"critical", "attention"}:
            conflicts.append(self._issue(
                "stable simulation + unstable runtime",
                "cognitive_conflict",
                "high",
                "Simulation stability conflicts with memory of Runtime instability.",
                "Prefer observed Runtime instability over optimistic simulation scenarios.",
            ))
        if strategy.get("automation_roadmap") and any(item.get("risk") == "critical" for item in fragile_assumptions):
            conflicts.append(self._issue(
                "aggressive roadmap + fragile architecture",
                "cognitive_conflict",
                "critical",
                "Roadmap expansion conflicts with fragile architectural assumptions.",
                "Reduce roadmap aggressiveness until fragile foundations are manually reviewed.",
            ))
        return conflicts

    @staticmethod
    def _issue(title: str, issue_type: str, risk: str, summary: str, recommendation: str) -> dict:
        return {
            "title": title,
            "type": issue_type,
            "risk": risk,
            "summary": summary,
            "recommendation": recommendation,
        }

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
            if normalized in {"critical", "blocked", "risky"}:
                return "low"
            if normalized in {"warning", "attention"}:
                return "medium"
            if normalized in {"healthy", "stable", "safe"}:
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

    @staticmethod
    def _titles(items: list[dict]) -> list[str]:
        return [str(item.get("title") or item.get("summary") or "") for item in items or []]

    @staticmethod
    def _contains_any(values: list[str], needles: list[str]) -> bool:
        haystack = " ".join(values).lower()
        return any(needle.lower() in haystack for needle in needles)

    @staticmethod
    def _has_priority(items, priority: str) -> bool:
        return any(str(item.get("priority") or item.get("severity") or "").lower() == priority for item in items or [])

    @staticmethod
    def _has_text(items, needles: list[str]) -> bool:
        text = " ".join(str(item) for item in items or []).lower()
        return any(needle.lower() in text for needle in needles)

    @staticmethod
    def _status(overconfidence: list[dict], governance: list[dict], conflicts: list[dict]) -> str:
        severe_governance = any(item.get("risk") == "critical" for item in governance)
        critical_conflicts = sum(1 for item in conflicts if item.get("risk") == "critical")
        if len(overconfidence) >= 2 or severe_governance or critical_conflicts >= 2:
            return "critical"
        if overconfidence or governance or conflicts:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(
        blind_spots: list[dict],
        uncertainty_sources: list[dict],
        overconfidence_risks: list[dict],
        governance_gaps: list[dict],
        cognitive_conflicts: list[dict],
    ) -> str:
        return (
            f"Detected {len(blind_spots)} blind spot(s), "
            f"{len(uncertainty_sources)} uncertainty source(s), "
            f"{len(overconfidence_risks)} overconfidence risk(s), "
            f"{len(governance_gaps)} governance gap(s), and "
            f"{len(cognitive_conflicts)} cognitive conflict(s)."
        )

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        actions = [
            "Keep Runtime meta-cognition read-only; do not automatically modify strategy, governance, SOP, or Runtime state.",
            "Use meta-cognition findings as manual review inputs, not executable decisions.",
        ]
        if status == "critical":
            actions.append("Resolve overconfidence, governance, and cognitive-conflict findings before expanding automation.")
        elif status == "attention":
            actions.append("Review uncertainty and blind-spot findings before relying on Runtime recommendations.")
        return actions
