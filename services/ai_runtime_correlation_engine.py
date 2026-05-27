"""Read-only correlation analysis engine for Runtime events and signals."""

from collections import Counter


class AIRuntimeCorrelationEngine:
    """Analyze event/signal relationships without executing any action."""

    KNOWN_CO_OCCURRENCES = [
        ("EXPORT_FAILED", "OPS_WARNING"),
        ("JSON_CORRUPTED", "SMOKE_TEST_FAILED"),
        ("RELEASE_BLOCKED", "OPS_CRITICAL"),
        ("TRUST_DECREASED", "BOUNDARY_RISK"),
        ("SMOKE_TEST_FAILED", "OPS_CRITICAL"),
        ("EXPORT_FAILED", "RELEASE_BLOCKED"),
    ]

    def analyze(self, events: list, signals: list) -> dict:
        events = [event for event in (events or []) if isinstance(event, dict)]
        signals = [signal for signal in (signals or []) if isinstance(signal, dict)]
        event_keys = [event.get("event_key") for event in events if event.get("event_key")]
        event_counts = Counter(event_keys)

        correlations = []
        root_cause_candidates = self._root_cause_candidates(event_counts)
        co_occurrence_patterns = self._co_occurrence_patterns(event_counts)
        impact_chains = self._impact_chains(event_counts)

        correlations.extend(self._same_layer_correlations(events))
        correlations.extend(self._repeated_pair_correlations(event_keys))
        correlations.extend(self._cross_layer_correlations(events))
        correlations.extend(self._signal_correlations(signals))
        correlations.extend(self._root_cause_correlations(root_cause_candidates))
        correlations.extend(self._impact_chain_correlations(impact_chains))
        correlations = self._dedupe_correlations(correlations)

        return {
            "correlations": correlations,
            "root_cause_candidates": root_cause_candidates,
            "co_occurrence_patterns": co_occurrence_patterns,
            "impact_chains": impact_chains,
            "correlation_summary": self._summary(correlations, root_cause_candidates, impact_chains),
            "recommended_actions": self._recommended_actions(correlations, root_cause_candidates, impact_chains),
        }

    @classmethod
    def confidence_for_count(cls, count: int) -> str:
        if count >= 3:
            return "high"
        if count == 2:
            return "medium"
        return "low"

    def _same_layer_correlations(self, events: list[dict]) -> list[dict]:
        by_layer = {}
        for event in events:
            layer = event.get("layer") or "unknown"
            by_layer.setdefault(layer, []).append(event.get("event_key"))
        correlations = []
        for layer, keys in by_layer.items():
            unique_keys = [key for key in dict.fromkeys(keys) if key]
            if len(unique_keys) >= 2:
                correlations.append(self._correlation(
                    unique_keys[0],
                    unique_keys[1],
                    "same_layer",
                    self.confidence_for_count(len(keys)),
                    f"{len(keys)} events co-exist in {layer}.",
                ))
        return correlations

    def _cross_layer_correlations(self, events: list[dict]) -> list[dict]:
        correlations = []
        for left, right in self.KNOWN_CO_OCCURRENCES:
            left_event = self._find_event(events, left)
            right_event = self._find_event(events, right)
            if left_event and right_event and left_event.get("layer") != right_event.get("layer"):
                correlations.append(self._correlation(
                    left,
                    right,
                    "cross_layer",
                    "medium",
                    f"{left} and {right} appear across Runtime layers.",
                ))
        return correlations

    def _repeated_pair_correlations(self, event_keys: list[str]) -> list[dict]:
        pair_counts = Counter()
        for index in range(len(event_keys) - 1):
            pair_counts[(event_keys[index], event_keys[index + 1])] += 1
        correlations = []
        for (source, target), count in pair_counts.items():
            if count >= 2:
                correlations.append(self._correlation(
                    source,
                    target,
                    "repeated_pair",
                    self.confidence_for_count(count),
                    f"{source} -> {target} repeated {count} times.",
                ))
        return correlations

    def _signal_correlations(self, signals: list[dict]) -> list[dict]:
        correlations = []
        risk_signals = [signal.get("signal_key") for signal in signals if signal.get("signal_key")]
        if "RELEASE_RISK_ESCALATION" in risk_signals and "CRITICAL_CLUSTER" in risk_signals:
            correlations.append(self._correlation(
                "CRITICAL_CLUSTER",
                "RELEASE_RISK_ESCALATION",
                "escalation_path",
                "medium",
                "Critical signal cluster appears with release risk escalation.",
            ))
        if "TRUST_COLLAPSE_RISK" in risk_signals and "POLICY_CONFLICT_PATTERN" in risk_signals:
            correlations.append(self._correlation(
                "TRUST_COLLAPSE_RISK",
                "POLICY_CONFLICT_PATTERN",
                "escalation_path",
                "medium",
                "Governance trust and policy conflict signals appear together.",
            ))
        return correlations

    def _root_cause_candidates(self, event_counts: Counter) -> list[dict]:
        candidates = []
        rules = [
            ("JSON_CORRUPTED", "OPS_WARNING", "JSON_CORRUPTED", "JSON instability may be affecting operations health."),
            ("EXPORT_FAILED", "RELEASE_BLOCKED", "EXPORT_FAILED", "Export instability may be blocking release readiness."),
            ("SMOKE_TEST_FAILED", "OPS_CRITICAL", "SMOKE_TEST_FAILED", "Smoke test failures may be driving critical ops health."),
            ("TRUST_DECREASED", "BOUNDARY_RISK", "TRUST_DECREASED", "Trust decrease and boundary risk suggest governance root cause."),
        ]
        for source, target, candidate, summary in rules:
            if event_counts[source] and event_counts[target]:
                evidence_count = max(event_counts[source], event_counts[target])
                candidates.append({
                    "candidate": candidate,
                    "evidence": [source, target],
                    "confidence": self.confidence_for_count(evidence_count),
                    "summary": summary,
                })
        return candidates

    def _co_occurrence_patterns(self, event_counts: Counter) -> list[dict]:
        patterns = []
        for source, target in self.KNOWN_CO_OCCURRENCES:
            if event_counts[source] and event_counts[target]:
                count = min(event_counts[source], event_counts[target])
                patterns.append({
                    "source": source,
                    "target": target,
                    "confidence": self.confidence_for_count(count),
                    "summary": f"{source} co-occurs with {target}.",
                })
        return patterns

    def _impact_chains(self, event_counts: Counter) -> list[dict]:
        chains = []
        if event_counts["JSON_CORRUPTED"] and (event_counts["SMOKE_TEST_FAILED"] or event_counts["OPS_WARNING"] or event_counts["OPS_CRITICAL"]):
            chain = ["JSON_CORRUPTED"]
            if event_counts["SMOKE_TEST_FAILED"]:
                chain.append("SMOKE_TEST_FAILED")
            if event_counts["OPS_CRITICAL"]:
                chain.append("OPS_CRITICAL")
            elif event_counts["OPS_WARNING"]:
                chain.append("OPS_WARNING")
            if event_counts["RELEASE_BLOCKED"]:
                chain.append("RELEASE_BLOCKED")
            chains.append(self._chain(chain, event_counts))

        if event_counts["EXPORT_FAILED"] and (event_counts["OPS_WARNING"] or event_counts["RELEASE_BLOCKED"]):
            chain = ["EXPORT_FAILED"]
            if event_counts["OPS_WARNING"]:
                chain.append("OPS_WARNING")
            if event_counts["RELEASE_BLOCKED"]:
                chain.append("RELEASE_BLOCKED")
            chains.append(self._chain(chain, event_counts))

        if event_counts["TRUST_DECREASED"] and event_counts["BOUNDARY_RISK"]:
            chain = ["TRUST_DECREASED", "BOUNDARY_RISK"]
            if event_counts["POLICY_GATE_BLOCKED"]:
                chain.append("POLICY_GATE_BLOCKED")
            chains.append(self._chain(chain, event_counts))
        return chains

    def _root_cause_correlations(self, candidates: list[dict]) -> list[dict]:
        return [
            self._correlation(
                (candidate.get("evidence") or [""])[0],
                candidate.get("candidate") or "",
                "cause_candidate",
                candidate.get("confidence") or "low",
                candidate.get("summary") or "",
            )
            for candidate in candidates
        ]

    def _impact_chain_correlations(self, chains: list[dict]) -> list[dict]:
        correlations = []
        for chain in chains:
            items = chain.get("chain") or []
            if len(items) >= 2:
                correlations.append(self._correlation(
                    items[0],
                    items[-1],
                    "escalation_path",
                    chain.get("confidence") or "low",
                    chain.get("summary") or "",
                ))
        return correlations

    @staticmethod
    def _find_event(events: list[dict], event_key: str) -> dict | None:
        for event in events:
            if event.get("event_key") == event_key:
                return event
        return None

    @staticmethod
    def _correlation(source: str, target: str, correlation_type: str, confidence: str, summary: str) -> dict:
        return {
            "source": source,
            "target": target,
            "correlation_type": correlation_type,
            "confidence": confidence,
            "summary": summary,
        }

    def _chain(self, chain: list[str], event_counts: Counter) -> dict:
        count = max(event_counts[item] for item in chain if item in event_counts)
        severity = "critical" if {"OPS_CRITICAL", "RELEASE_BLOCKED", "POLICY_GATE_BLOCKED"} & set(chain) else "attention"
        return {
            "chain": chain,
            "severity": severity,
            "confidence": self.confidence_for_count(count),
            "summary": " -> ".join(chain),
        }

    @staticmethod
    def _dedupe_correlations(correlations: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for correlation in correlations:
            key = (correlation.get("source"), correlation.get("target"), correlation.get("correlation_type"))
            if key in seen:
                continue
            seen.add(key)
            result.append(correlation)
        return result

    @staticmethod
    def _summary(correlations: list[dict], candidates: list[dict], chains: list[dict]) -> str:
        if candidates or chains:
            return f"Detected {len(correlations)} correlations, {len(candidates)} root cause candidates, and {len(chains)} impact chains."
        if correlations:
            return f"Detected {len(correlations)} read-only Runtime correlations."
        return "No obvious Runtime correlation risk detected."

    @staticmethod
    def _recommended_actions(correlations: list[dict], candidates: list[dict], chains: list[dict]) -> list[str]:
        actions = []
        if candidates:
            actions.append("Manually review root cause candidates before changing any Runtime process.")
        if chains:
            actions.append("Use impact chains for read-only diagnosis; do not trigger automatic recovery.")
        if correlations:
            actions.append("Keep correlation analysis read-only and verify with existing Dashboard centers.")
        return actions or ["Keep Runtime correlation analysis in observation mode."]
