"""Read-only Runtime simulation engine for decision and risk scenarios."""


class AIRuntimeSimulationEngine:
    """Simulate Runtime outcomes without executing actions."""

    TYPE_MAP = {
        "intervention": "intervention",
        "release": "release",
        "rollback": "rollback",
        "observation": "observation",
        "governance": "governance",
        "recovery": "recovery",
        "export": "export",
        "ops": "ops",
        "escalation": "recovery",
    }

    def simulate(self, decisions, causal_graph, intervention_center, signal_center) -> dict:
        decisions = [item for item in (decisions or []) if isinstance(item, dict)]
        causal_graph = causal_graph or {}
        intervention_center = intervention_center or {}
        signal_center = signal_center or {}

        simulations = [self._simulation_from_decision(item) for item in decisions]
        simulations.extend(self._simulations_from_interventions(intervention_center))
        simulations = self._dedupe_simulations(simulations)

        best_case_scenarios = self._best_cases(simulations, signal_center)
        worst_case_scenarios = self._worst_cases(simulations, causal_graph, signal_center)
        risk_propagation_forecasts = self._risk_forecasts(causal_graph)
        rollback_impacts = self._rollback_impacts(decisions)

        return {
            "simulations": simulations,
            "best_case_scenarios": best_case_scenarios,
            "worst_case_scenarios": worst_case_scenarios,
            "risk_propagation_forecasts": risk_propagation_forecasts,
            "rollback_impacts": rollback_impacts,
            "simulation_summary": self._summary(simulations, worst_case_scenarios, risk_propagation_forecasts),
            "recommended_actions": self._recommended_actions(worst_case_scenarios, risk_propagation_forecasts),
        }

    def _simulation_from_decision(self, decision: dict) -> dict:
        decision_type = self.TYPE_MAP.get(decision.get("decision_type"), "observation")
        status = decision.get("decision_status") or "observe_only"
        priority = decision.get("priority") or "medium"
        risk_level = self._risk_level(decision)
        rollback_available = bool(decision.get("rollback_plan"))

        if status == "recommended":
            runtime_effect = "Runtime remains in read-only observation while recommended decision is reviewed."
            stability_change = "improve"
            trust_change = "stable"
            confidence_change = "improve" if decision.get("confidence") != "low" else "stable"
        elif status == "blocked":
            runtime_effect = "Risk remains contained only if blocked decision is not executed."
            stability_change = "degrade_if_ignored"
            trust_change = "decrease"
            confidence_change = "decrease"
        elif status == "manual_only":
            runtime_effect = "Runtime outcome depends on manual review quality; no automatic action is safe."
            stability_change = "stable_if_reviewed"
            trust_change = "stable"
            confidence_change = "stable"
        else:
            runtime_effect = "Observation-only decision keeps Runtime unchanged."
            stability_change = "stable"
            trust_change = "stable"
            confidence_change = "stable"

        return {
            "title": f"Simulate decision: {decision.get('title') or decision_type}",
            "simulation_type": decision_type,
            "target": decision.get("title") or decision_type,
            "expected_runtime_effect": runtime_effect,
            "stability_change": stability_change,
            "trust_change": trust_change,
            "confidence_change": confidence_change,
            "risk_level": risk_level,
            "rollback_available": rollback_available,
            "summary": decision.get("risk") or runtime_effect,
        }

    def _simulations_from_interventions(self, intervention_center: dict) -> list[dict]:
        simulations = []
        for item in intervention_center.get("root_cause_interventions") or []:
            simulations.append({
                "title": f"Simulate intervention success: {item.get('target')}",
                "simulation_type": self.TYPE_MAP.get(item.get("intervention_type"), "intervention"),
                "target": item.get("target") or "",
                "expected_runtime_effect": "If manual intervention succeeds, upstream risk propagation may slow.",
                "stability_change": "improve_if_successful",
                "trust_change": "stable",
                "confidence_change": "improve",
                "risk_level": "medium" if item.get("priority") != "critical" else "high",
                "rollback_available": True,
                "summary": item.get("expected_effect") or "Manual intervention success may improve Runtime stability.",
            })
        for item in intervention_center.get("blocking_interventions") or []:
            simulations.append({
                "title": f"Simulate propagation blocking: {item.get('target')}",
                "simulation_type": "recovery",
                "target": item.get("target") or "",
                "expected_runtime_effect": "If manually blocked, risk may stop before release or governance impact.",
                "stability_change": "improve_if_successful",
                "trust_change": "stable",
                "confidence_change": "stable",
                "risk_level": "critical" if item.get("priority") == "critical" else "high",
                "rollback_available": True,
                "summary": item.get("reason") or "Manual blocking can reduce propagation risk.",
            })
        return simulations

    def _best_cases(self, simulations: list[dict], signal_center: dict) -> list[dict]:
        cases = []
        if simulations:
            cases.append(self._scenario(
                "critical events reduce after manual review",
                "critical events 减少，Timeline 恢复稳定。",
                "medium",
            ))
            cases.append(self._scenario(
                "ops health improves",
                "Ops Health 提升，Runtime stability 未来变化转为 stable。",
                "medium",
            ))
        if signal_center.get("signal_status") in {"stable", "warning", "critical"}:
            cases.append(self._scenario(
                "trust and confidence stabilize",
                "Trust/Confidence 在人工复核后保持稳定或提升。",
                "low",
            ))
        return cases or [self._scenario("baseline observation remains stable", "只读观察保持 Runtime 不变。", "low")]

    def _worst_cases(self, simulations: list[dict], causal_graph: dict, signal_center: dict) -> list[dict]:
        cases = []
        has_critical_simulation = any(item.get("risk_level") == "critical" for item in simulations)
        if has_critical_simulation:
            cases.append(self._scenario("event storm", "忽略 critical 决策可能导致 event storm。", "critical"))
        if causal_graph.get("critical_paths"):
            cases.append(self._scenario("release blocked", "关键因果链继续传播可能导致 release blocked。", "critical"))
        critical_signals = signal_center.get("critical_signals") or []
        if critical_signals:
            cases.append(self._scenario("trust collapse", "critical signal 聚集可能导致 trust/confidence 下降。", "high"))
        if any(not item.get("rollback_available") for item in simulations):
            cases.append(self._scenario("rollback unavailable", "缺少 rollback 方案会扩大恢复不确定性。", "critical"))
        return cases

    def _risk_forecasts(self, causal_graph: dict) -> list[dict]:
        forecasts = []
        for item in causal_graph.get("critical_paths") or []:
            path = item.get("path") or []
            if not path:
                continue
            forecasts.append({
                "path": path,
                "risk_level": "critical" if item.get("severity") == "critical" else "high",
                "summary": " -> ".join(path),
            })
        for item in causal_graph.get("root_causes") or []:
            node_id = item.get("node_id") or ""
            if node_id == "JSON_CORRUPTED":
                forecasts.append({
                    "path": ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_WARNING", "RELEASE_BLOCKED"],
                    "risk_level": "critical" if item.get("confidence") == "high" else "high",
                    "summary": "JSON corruption may propagate through smoke test, ops, and release readiness.",
                })
            elif node_id == "EXPORT_FAILED":
                forecasts.append({
                    "path": ["EXPORT_FAILED", "OPS_WARNING", "RELEASE_BLOCKED"],
                    "risk_level": "high",
                    "summary": "Export failure may escalate into ops warning and release blockage.",
                })
        return self._dedupe_forecasts(forecasts)

    def _rollback_impacts(self, decisions: list[dict]) -> list[dict]:
        impacts = []
        for decision in decisions:
            rollback_plan = decision.get("rollback_plan")
            if not rollback_plan:
                continue
            impacts.append({
                "target": decision.get("title") or "",
                "rollback_plan": rollback_plan,
                "expected_impact": self._rollback_impact(rollback_plan),
                "risk_level": "medium" if decision.get("priority") != "critical" else "high",
            })
        return impacts

    @staticmethod
    def _rollback_impact(rollback_plan: str) -> str:
        plan = rollback_plan.lower()
        if "json" in plan:
            return "restore json backup may stabilize Runtime reads but needs manual validation."
        if "export" in plan:
            return "restore export state may reduce export instability."
        if "release" in plan:
            return "release rollback keeps release readiness in manual review."
        if "configuration" in plan:
            return "runtime config revert may reduce instability after manual review."
        return "rollback returns Runtime to observe-only diagnosis."

    @staticmethod
    def _risk_level(decision: dict) -> str:
        if decision.get("decision_status") == "blocked" or decision.get("priority") == "critical":
            return "critical"
        if decision.get("trust_level") == "low" or decision.get("confidence") == "low":
            return "high"
        if decision.get("decision_status") == "manual_only":
            return "medium"
        return "low"

    @staticmethod
    def _scenario(title: str, summary: str, risk_level: str) -> dict:
        return {
            "title": title,
            "risk_level": risk_level,
            "summary": summary,
        }

    @staticmethod
    def _dedupe_simulations(simulations: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in simulations:
            key = (item.get("title"), item.get("simulation_type"), item.get("target"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _dedupe_forecasts(forecasts: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in forecasts:
            key = tuple(item.get("path") or [])
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _summary(simulations: list[dict], worst_cases: list[dict], forecasts: list[dict]) -> str:
        return (
            f"Generated {len(simulations)} simulation(s), "
            f"{len(worst_cases)} worst-case scenario(s), and "
            f"{len(forecasts)} risk propagation forecast(s)."
        )

    @staticmethod
    def _recommended_actions(worst_cases: list[dict], forecasts: list[dict]) -> list[str]:
        actions = []
        if worst_cases:
            actions.append("Keep worst-case scenarios as read-only warnings; do not trigger automatic recovery.")
        if forecasts:
            actions.append("Use propagation forecasts for manual review before any Runtime change.")
        return actions or ["Keep Runtime simulation in read-only observation mode."]
