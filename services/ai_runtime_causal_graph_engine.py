"""Read-only causal graph inference for Runtime events, signals, and correlations."""

from collections import Counter


class AIRuntimeCausalGraphEngine:
    """Build a lightweight Runtime causal graph without executing any action."""

    SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}

    CAUSAL_RULES = [
        ("JSON_CORRUPTED", "SMOKE_TEST_FAILED", "destabilizes", "JSON corruption can destabilize smoke checks."),
        ("JSON_CORRUPTED", "OPS_WARNING", "propagates_to", "JSON corruption can propagate into ops warnings."),
        ("JSON_CORRUPTED", "OPS_CRITICAL", "propagates_to", "JSON corruption can propagate into critical ops health."),
        ("SMOKE_TEST_FAILED", "OPS_WARNING", "escalates", "Smoke test failure can escalate into ops warning."),
        ("SMOKE_TEST_FAILED", "OPS_CRITICAL", "escalates", "Smoke test failure can escalate into critical ops health."),
        ("OPS_WARNING", "RELEASE_BLOCKED", "blocks", "Ops warning can block release readiness."),
        ("OPS_CRITICAL", "RELEASE_BLOCKED", "blocks", "Critical ops health can block release readiness."),
        ("EXPORT_FAILED", "OPS_WARNING", "destabilizes", "Export failures can destabilize operations."),
        ("EXPORT_FAILED", "RELEASE_BLOCKED", "blocks", "Export failures can block release readiness."),
        ("TRUST_DECREASED", "BOUNDARY_RISK", "weakens", "Trust decrease can weaken governance boundaries."),
        ("BOUNDARY_RISK", "POLICY_GATE_BLOCKED", "blocks", "Boundary risk can block policy gates."),
    ]

    CORRELATION_RELATIONSHIP_MAP = {
        "cause_candidate": "likely_causes",
        "escalation_path": "escalates",
        "repeated_pair": "propagates_to",
        "cross_layer": "propagates_to",
        "same_layer": "destabilizes",
    }

    ROOT_CAUSE_KEYS = {"JSON_CORRUPTED", "EXPORT_FAILED", "SMOKE_TEST_FAILED", "TRUST_DECREASED"}
    SYMPTOM_KEYS = {"RELEASE_BLOCKED", "POLICY_GATE_BLOCKED", "OPS_CRITICAL"}

    def build_graph(self, events, signals, correlations) -> dict:
        events = [item for item in (events or []) if isinstance(item, dict)]
        signals = [item for item in (signals or []) if isinstance(item, dict)]
        correlations = [item for item in (correlations or []) if isinstance(item, dict)]

        event_counts = Counter(event.get("event_key") for event in events if event.get("event_key"))
        event_severities = self._event_severities(events)
        nodes = self._event_nodes(event_counts, event_severities)
        nodes.extend(self._signal_nodes(signals))

        edges = []
        edges.extend(self._rule_edges(event_counts))
        edges.extend(self._correlation_edges(correlations))
        edges = self._dedupe_edges(edges)

        root_causes = self._root_causes(event_counts, event_severities, edges)
        symptoms = self._symptoms(event_counts, event_severities, edges)
        fragile_nodes = self._fragile_nodes(event_counts, edges)
        critical_paths = self._critical_paths(event_counts)

        return {
            "nodes": nodes,
            "edges": edges,
            "root_causes": root_causes,
            "symptoms": symptoms,
            "fragile_nodes": fragile_nodes,
            "critical_paths": critical_paths,
            "causal_summary": self._summary(root_causes, symptoms, fragile_nodes, critical_paths),
            "recommended_actions": self._recommended_actions(root_causes, fragile_nodes, critical_paths),
        }

    @classmethod
    def confidence_for_count(cls, count: int) -> str:
        if count >= 3:
            return "high"
        if count == 2:
            return "medium"
        return "low"

    def _event_nodes(self, event_counts: Counter, event_severities: dict) -> list[dict]:
        return [
            {
                "node_id": key,
                "type": "event",
                "severity": event_severities.get(key) or "info",
                "frequency": count,
                "summary": f"{key} appeared {count} time(s).",
            }
            for key, count in event_counts.items()
        ]

    def _signal_nodes(self, signals: list[dict]) -> list[dict]:
        signal_counts = Counter(signal.get("signal_key") for signal in signals if signal.get("signal_key"))
        severities = {}
        for signal in signals:
            key = signal.get("signal_key")
            if not key:
                continue
            severities[key] = self._max_severity(severities.get(key), signal.get("severity") or "info")
        return [
            {
                "node_id": key,
                "type": "signal",
                "severity": severities.get(key) or "info",
                "frequency": count,
                "summary": f"{key} signal appeared {count} time(s).",
            }
            for key, count in signal_counts.items()
        ]

    def _rule_edges(self, event_counts: Counter) -> list[dict]:
        edges = []
        for source, target, relationship, summary in self.CAUSAL_RULES:
            if event_counts[source] and event_counts[target]:
                count = max(event_counts[source], event_counts[target])
                edges.append(self._edge(source, target, relationship, self.confidence_for_count(count), summary))
        return edges

    def _correlation_edges(self, correlations: list[dict]) -> list[dict]:
        edges = []
        for item in correlations:
            source = item.get("source")
            target = item.get("target")
            if not source or not target:
                continue
            relationship = self.CORRELATION_RELATIONSHIP_MAP.get(
                item.get("correlation_type"),
                "propagates_to",
            )
            edges.append(self._edge(
                source,
                target,
                relationship,
                item.get("confidence") or "low",
                item.get("summary") or f"{source} may affect {target}.",
            ))
        return edges

    def _root_causes(self, event_counts: Counter, event_severities: dict, edges: list[dict]) -> list[dict]:
        out_degree = Counter(edge.get("source") for edge in edges if edge.get("source"))
        roots = []
        for key in self.ROOT_CAUSE_KEYS:
            if not event_counts[key] or not out_degree[key]:
                continue
            confidence = self.confidence_for_count(max(event_counts[key], out_degree[key]))
            roots.append({
                "node_id": key,
                "type": "root_cause",
                "severity": event_severities.get(key) or "warning",
                "frequency": event_counts[key],
                "confidence": confidence,
                "summary": f"{key} is a possible propagation source across {out_degree[key]} causal edge(s).",
            })
        return sorted(roots, key=lambda item: (-item["frequency"], item["node_id"]))

    def _symptoms(self, event_counts: Counter, event_severities: dict, edges: list[dict]) -> list[dict]:
        incoming = Counter(edge.get("target") for edge in edges if edge.get("target"))
        outgoing = Counter(edge.get("source") for edge in edges if edge.get("source"))
        symptoms = []
        for key in self.SYMPTOM_KEYS:
            if not event_counts[key] or not incoming[key]:
                continue
            if outgoing[key] > incoming[key]:
                continue
            symptoms.append({
                "node_id": key,
                "type": "symptom",
                "severity": event_severities.get(key) or "warning",
                "frequency": event_counts[key],
                "confidence": self.confidence_for_count(incoming[key]),
                "summary": f"{key} appears more like a downstream symptom than a source.",
            })
        return sorted(symptoms, key=lambda item: (item["node_id"]))

    def _fragile_nodes(self, event_counts: Counter, edges: list[dict]) -> list[dict]:
        incoming = Counter(edge.get("target") for edge in edges if edge.get("target"))
        outgoing = Counter(edge.get("source") for edge in edges if edge.get("source"))
        fragile = []
        if event_counts["JSON_CORRUPTED"] >= 2 or outgoing["JSON_CORRUPTED"] >= 2:
            fragile.append(self._fragile("JSON Store", event_counts["JSON_CORRUPTED"], outgoing["JSON_CORRUPTED"]))
        ops_frequency = event_counts["OPS_WARNING"] + event_counts["OPS_CRITICAL"]
        ops_degree = incoming["OPS_WARNING"] + incoming["OPS_CRITICAL"] + outgoing["OPS_WARNING"] + outgoing["OPS_CRITICAL"]
        if ops_frequency >= 2 or ops_degree >= 2:
            fragile.append(self._fragile("Ops Health", ops_frequency, ops_degree))
        if event_counts["EXPORT_FAILED"] >= 2 or outgoing["EXPORT_FAILED"] >= 2:
            fragile.append(self._fragile("Export Operations", event_counts["EXPORT_FAILED"], outgoing["EXPORT_FAILED"]))
        return fragile

    def _critical_paths(self, event_counts: Counter) -> list[dict]:
        paths = []
        if event_counts["JSON_CORRUPTED"] and event_counts["RELEASE_BLOCKED"]:
            path = ["JSON_CORRUPTED"]
            if event_counts["SMOKE_TEST_FAILED"]:
                path.append("SMOKE_TEST_FAILED")
            if event_counts["OPS_CRITICAL"]:
                path.append("OPS_CRITICAL")
            elif event_counts["OPS_WARNING"]:
                path.append("OPS_WARNING")
            path.append("RELEASE_BLOCKED")
            paths.append(self._path(path, event_counts))

        if event_counts["EXPORT_FAILED"] and event_counts["RELEASE_BLOCKED"]:
            path = ["EXPORT_FAILED"]
            if event_counts["OPS_WARNING"]:
                path.append("OPS_WARNING")
            path.append("RELEASE_BLOCKED")
            paths.append(self._path(path, event_counts))

        if event_counts["TRUST_DECREASED"] and event_counts["POLICY_GATE_BLOCKED"]:
            path = ["TRUST_DECREASED", "BOUNDARY_RISK", "POLICY_GATE_BLOCKED"]
            paths.append(self._path(path, event_counts))
        return paths

    @staticmethod
    def _edge(source: str, target: str, relationship: str, confidence: str, summary: str) -> dict:
        return {
            "source": source,
            "target": target,
            "relationship": relationship,
            "confidence": confidence,
            "summary": summary,
        }

    def _path(self, path: list[str], event_counts: Counter) -> dict:
        count = max(event_counts[item] for item in path if event_counts[item])
        severity = "critical" if {"RELEASE_BLOCKED", "POLICY_GATE_BLOCKED", "OPS_CRITICAL"} & set(path) else "warning"
        return {
            "path": path,
            "severity": severity,
            "confidence": self.confidence_for_count(count),
            "summary": " -> ".join(path),
        }

    @staticmethod
    def _fragile(node_id: str, frequency: int, degree: int) -> dict:
        return {
            "node_id": node_id,
            "type": "fragile_node",
            "severity": "warning" if max(frequency, degree) < 3 else "critical",
            "frequency": frequency,
            "confidence": AIRuntimeCausalGraphEngine.confidence_for_count(max(frequency, degree)),
            "summary": f"{node_id} has {frequency} event(s) and {degree} causal dependency edge(s).",
        }

    @classmethod
    def _event_severities(cls, events: list[dict]) -> dict:
        severities = {}
        for event in events:
            key = event.get("event_key")
            if not key:
                continue
            severities[key] = cls._max_severity(severities.get(key), event.get("severity") or "info")
        return severities

    @classmethod
    def _max_severity(cls, current: str | None, candidate: str) -> str:
        current = current or "info"
        return candidate if cls.SEVERITY_RANK.get(candidate, 0) > cls.SEVERITY_RANK.get(current, 0) else current

    @staticmethod
    def _dedupe_edges(edges: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for edge in edges:
            key = (edge.get("source"), edge.get("target"), edge.get("relationship"))
            if key in seen:
                continue
            seen.add(key)
            result.append(edge)
        return result

    @staticmethod
    def _summary(root_causes: list[dict], symptoms: list[dict], fragile_nodes: list[dict], paths: list[dict]) -> str:
        if root_causes or paths:
            return (
                f"Detected {len(root_causes)} possible root cause(s), "
                f"{len(symptoms)} symptom(s), {len(fragile_nodes)} fragile node(s), "
                f"and {len(paths)} critical path(s)."
            )
        if fragile_nodes:
            return f"Detected {len(fragile_nodes)} fragile Runtime node(s) for read-only observation."
        return "No obvious Runtime causal risk detected."

    @staticmethod
    def _recommended_actions(root_causes: list[dict], fragile_nodes: list[dict], paths: list[dict]) -> list[str]:
        actions = []
        if root_causes:
            actions.append("Manually review likely root causes before changing any Runtime process.")
        if paths:
            actions.append("Use critical paths for read-only diagnosis; do not trigger automatic recovery.")
        if fragile_nodes:
            actions.append("Watch fragile nodes through existing Dashboard centers without writing business state.")
        return actions or ["Keep Runtime causal graph inference in observation mode."]
