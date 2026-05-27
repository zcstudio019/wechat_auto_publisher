"""Read-only Runtime decision recommendation engine."""


class AIRuntimeDecisionEngine:
    """Build Runtime decision recommendations without executing decisions."""

    MANUAL_ONLY_TARGETS = {
        "release",
        "publish",
        "approval",
        "governance",
        "boundary",
        "constitution",
        "prompt/template/content mutation",
    }

    def build_decisions(
        self,
        intervention_center,
        causal_graph_center,
        policy_gate_center,
        constitution_center,
        trust_center,
        confidence_center,
    ) -> dict:
        intervention_center = intervention_center or {}
        causal_graph_center = causal_graph_center or {}
        policy_gate_center = policy_gate_center or {}
        constitution_center = constitution_center or {}
        trust_center = trust_center or {}
        confidence_center = confidence_center or {}

        context = self._context(policy_gate_center, constitution_center, trust_center, confidence_center)
        decisions = []
        decisions.extend(self._intervention_decisions(intervention_center, context))
        decisions.extend(self._causal_decisions(causal_graph_center, context))
        decisions.append(self._observation_decision(context))
        decisions = self._dedupe_decisions(decisions)

        recommended_decisions = [
            item for item in decisions
            if item.get("decision_status") == "recommended"
            and item.get("constitution_safe") is True
            and item.get("boundary_safe") is True
            and item.get("trust_level") != "low"
        ]
        blocked_decisions = [item for item in decisions if item.get("decision_status") == "blocked"]
        manual_only_decisions = [item for item in decisions if item.get("decision_status") == "manual_only"]
        high_risk_decisions = [item for item in decisions if self._is_high_risk(item)]
        rollback_candidates = self._rollback_candidates(decisions, causal_graph_center)

        return {
            "decisions": decisions,
            "recommended_decisions": recommended_decisions,
            "blocked_decisions": blocked_decisions,
            "manual_only_decisions": manual_only_decisions,
            "high_risk_decisions": high_risk_decisions,
            "rollback_candidates": rollback_candidates,
            "decision_summary": self._summary(recommended_decisions, blocked_decisions, manual_only_decisions, high_risk_decisions),
            "recommended_actions": self._recommended_actions(blocked_decisions, manual_only_decisions, high_risk_decisions),
        }

    def _intervention_decisions(self, intervention_center: dict, context: dict) -> list[dict]:
        decisions = []
        for item in intervention_center.get("interventions") or []:
            target = item.get("target") or "unknown"
            decision_type = self._decision_type(item.get("intervention_type"), target)
            status = self._decision_status(item, context, decision_type)
            decisions.append(self._decision(
                title=f"Review intervention: {item.get('title') or target}",
                decision_type=decision_type,
                priority=item.get("priority") or "medium",
                decision_status=status,
                confidence=context["confidence_level"],
                trust_level=context["trust_level"],
                constitution_safe=context["constitution_safe"],
                boundary_safe=context["boundary_safe"],
                manual_required=True,
                reason=item.get("reason") or "Runtime intervention requires read-only decision review.",
                risk=self._risk(status, context, item),
                rollback_plan=self._rollback_plan(target, decision_type),
            ))
        return decisions

    def _causal_decisions(self, causal_graph_center: dict, context: dict) -> list[dict]:
        decisions = []
        for item in causal_graph_center.get("root_causes") or []:
            target = item.get("node_id") or "root_cause"
            status = "blocked" if context["blocked"] else "manual_only"
            decisions.append(self._decision(
                title=f"Decide root cause response: {target}",
                decision_type="intervention",
                priority="critical" if item.get("confidence") == "high" else "high",
                decision_status=status,
                confidence=item.get("confidence") or context["confidence_level"],
                trust_level=context["trust_level"],
                constitution_safe=context["constitution_safe"],
                boundary_safe=context["boundary_safe"],
                manual_required=True,
                reason=f"{target} is a possible root cause and must be reviewed manually.",
                risk="Root-cause response may affect downstream Runtime centers if done without review.",
                rollback_plan=self._rollback_plan(target, "intervention"),
            ))
        for item in causal_graph_center.get("critical_paths") or []:
            path = " -> ".join(item.get("path") or []) or "critical_path"
            decisions.append(self._decision(
                title="Escalate critical causal path",
                decision_type="escalation",
                priority="critical",
                decision_status="blocked" if context["blocked"] else "manual_only",
                confidence=item.get("confidence") or context["confidence_level"],
                trust_level=context["trust_level"],
                constitution_safe=context["constitution_safe"],
                boundary_safe=context["boundary_safe"],
                manual_required=True,
                reason=f"Critical path requires manual escalation review: {path}.",
                risk="High escalation risk if release, recovery, or governance decisions bypass manual review.",
                rollback_plan="Return to observe-only mode and re-check causal graph before any Runtime change.",
            ))
        return decisions

    def _observation_decision(self, context: dict) -> dict:
        status = "blocked" if context["blocked"] else "recommended"
        return self._decision(
            title="Continue read-only Runtime observation",
            decision_type="observation",
            priority="medium",
            decision_status=status,
            confidence=context["confidence_level"],
            trust_level=context["trust_level"],
            constitution_safe=context["constitution_safe"],
            boundary_safe=context["boundary_safe"],
            manual_required=True,
            reason="Observation is the only automatically safe recommendation boundary for this layer.",
            risk="Low execution risk because no action is performed.",
            rollback_plan="Stop recommendation display and return to previous dashboard snapshot.",
        )

    def _context(self, policy_gate: dict, constitution: dict, trust: dict, confidence: dict) -> dict:
        gate_status = self._first_value(policy_gate, ["gate_status", "policy_gate_status", "status"])
        constitution_status = self._first_value(constitution, ["constitution_status", "status"])
        boundary_status = self._first_value(policy_gate, ["boundary_status"]) or self._first_value(constitution, ["boundary_status"])
        trust_level = self._trust_level(trust)
        confidence_level = self._confidence_level(confidence)

        policy_blocked = gate_status in {"blocked", "closed", "deny", "critical", "violation"}
        constitution_safe = constitution_status not in {"unsafe", "conflict", "violation", "blocked", "critical"}
        boundary_safe = boundary_status not in {"unsafe", "violated", "blocked", "critical"}
        return {
            "gate_status": gate_status or "unknown",
            "constitution_status": constitution_status or "unknown",
            "trust_level": trust_level,
            "confidence_level": confidence_level,
            "constitution_safe": constitution_safe,
            "boundary_safe": boundary_safe,
            "blocked": policy_blocked or not constitution_safe or not boundary_safe,
        }

    def _decision_status(self, intervention: dict, context: dict, decision_type: str) -> str:
        target = intervention.get("target") or ""
        if context["blocked"]:
            return "blocked"
        if target in self.MANUAL_ONLY_TARGETS or decision_type in {"release", "governance", "recovery", "escalation"}:
            return "manual_only"
        if context["trust_level"] == "low" or context["confidence_level"] == "low":
            return "observe_only"
        return "recommended"

    @staticmethod
    def _decision(
        title: str,
        decision_type: str,
        priority: str,
        decision_status: str,
        confidence: str,
        trust_level: str,
        constitution_safe: bool,
        boundary_safe: bool,
        manual_required: bool,
        reason: str,
        risk: str,
        rollback_plan: str,
    ) -> dict:
        return {
            "title": title,
            "decision_type": decision_type,
            "priority": priority,
            "decision_status": decision_status,
            "confidence": confidence,
            "trust_level": trust_level,
            "constitution_safe": constitution_safe,
            "boundary_safe": boundary_safe,
            "manual_required": manual_required,
            "reason": reason,
            "risk": risk,
            "rollback_plan": rollback_plan,
        }

    @staticmethod
    def _decision_type(intervention_type: str | None, target: str) -> str:
        if intervention_type in {"release", "ops", "export", "governance"}:
            return intervention_type
        if intervention_type == "json":
            return "ops"
        if intervention_type == "blocking":
            return "escalation"
        if target in {"release", "publish", "approval"}:
            return "release"
        if "export" in target.lower():
            return "export"
        return "intervention"

    @staticmethod
    def _risk(status: str, context: dict, intervention: dict) -> str:
        if status == "blocked":
            return "Decision is blocked by policy, constitution, or boundary checks."
        if context["trust_level"] == "low" or context["confidence_level"] == "low":
            return "Low trust or confidence makes this decision high risk."
        if intervention.get("priority") == "critical":
            return "Critical priority requires manual review before any operational change."
        return "Decision is read-only and must remain manually reviewed."

    @staticmethod
    def _rollback_plan(target: str, decision_type: str) -> str:
        target_upper = (target or "").upper()
        if "JSON" in target_upper:
            return "Restore JSON backup and re-check Runtime state before changing configuration."
        if "EXPORT" in target_upper or decision_type == "export":
            return "Restore export state and re-run read-only export validation."
        if "RELEASE" in target_upper or decision_type == "release":
            return "Rollback release readiness decision and return release to manual review."
        if decision_type == "governance":
            return "Revert to previous governance decision snapshot and request manual review."
        return "Return to observe-only mode and re-run Runtime diagnostics."

    def _rollback_candidates(self, decisions: list[dict], causal_graph: dict) -> list[dict]:
        candidates = []
        for decision in decisions:
            if decision.get("priority") in {"critical", "high"} or decision.get("decision_status") in {"blocked", "manual_only"}:
                candidates.append({
                    "decision": decision.get("title") or "",
                    "rollback_plan": decision.get("rollback_plan") or "",
                    "reason": decision.get("risk") or "",
                })
        for item in causal_graph.get("root_causes") or []:
            target = item.get("node_id") or ""
            if target == "JSON_CORRUPTED":
                candidates.append({
                    "decision": "restore json backup",
                    "rollback_plan": "Restore JSON backup before any Runtime configuration change.",
                    "reason": "JSON root cause can propagate through multiple Runtime centers.",
                })
        return self._dedupe_rollbacks(candidates)

    @staticmethod
    def _is_high_risk(decision: dict) -> bool:
        return (
            decision.get("trust_level") == "low"
            or decision.get("confidence") == "low"
            or decision.get("priority") == "critical"
            or not decision.get("rollback_plan")
            or decision.get("decision_status") == "blocked"
        )

    @staticmethod
    def _trust_level(trust: dict) -> str:
        value = AIRuntimeDecisionEngine._first_value(trust, ["trust_status", "trust_level", "status"])
        if not value and isinstance(trust.get("global_trust"), dict):
            value = AIRuntimeDecisionEngine._first_value(trust.get("global_trust"), ["level", "status"])
        if value in {"high", "trusted", "normal", "healthy"}:
            return "high"
        if value in {"low", "weak", "decreased", "critical"}:
            return "low"
        return value or "medium"

    @staticmethod
    def _confidence_level(confidence: dict) -> str:
        value = AIRuntimeDecisionEngine._first_value(confidence, ["confidence_status", "confidence_level", "status"])
        if value in {"high", "medium", "low"}:
            return value
        if value in {"critical", "weak"}:
            return "low"
        if value in {"normal", "healthy"}:
            return "high"
        return "medium"

    @staticmethod
    def _first_value(source: dict, keys: list[str]) -> str:
        for key in keys:
            value = source.get(key)
            if value is not None:
                return str(value).lower()
        return ""

    @staticmethod
    def _dedupe_decisions(decisions: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for decision in decisions:
            key = (decision.get("title"), decision.get("decision_type"), decision.get("decision_status"))
            if key in seen:
                continue
            seen.add(key)
            result.append(decision)
        return result

    @staticmethod
    def _dedupe_rollbacks(candidates: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in candidates:
            key = (item.get("decision"), item.get("rollback_plan"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _summary(recommended: list, blocked: list, manual_only: list, high_risk: list) -> str:
        return (
            f"Generated {len(recommended)} recommended decision(s), "
            f"{len(blocked)} blocked decision(s), {len(manual_only)} manual-only decision(s), "
            f"and {len(high_risk)} high-risk decision(s)."
        )

    @staticmethod
    def _recommended_actions(blocked: list, manual_only: list, high_risk: list) -> list[str]:
        actions = []
        if blocked:
            actions.append("Do not execute blocked Runtime decisions; review policy, constitution, and boundary status manually.")
        if high_risk:
            actions.append("Escalate high-risk decisions for manual review before any operational change.")
        if manual_only:
            actions.append("Keep release, publish, approval, governance, Prompt, template, and content decisions manual-only.")
        return actions or ["Keep Runtime decisions in read-only recommendation mode."]
