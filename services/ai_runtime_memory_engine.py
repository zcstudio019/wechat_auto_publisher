"""Read-only cognitive memory analysis for AI Runtime OS."""

from collections import Counter


class AIRuntimeMemoryEngine:
    """Build Runtime cognitive memory insights without mutating Runtime state."""

    def build_memory(self, events, signals, correlations, causal_graph, strategy_center) -> dict:
        events = [item for item in (events or []) if isinstance(item, dict)]
        signals = [item for item in (signals or []) if isinstance(item, dict)]
        correlations = [item for item in (correlations or []) if isinstance(item, dict)]
        causal_graph = causal_graph or {}
        strategy_center = strategy_center or {}

        recent_memories = self._runtime_memories(events, signals, causal_graph, strategy_center)
        repeated_patterns = self._repeated_patterns(events, signals, causal_graph, strategy_center)
        governance_lessons = self._governance_lessons(events, signals, strategy_center)
        stability_lessons = self._stability_lessons(events, causal_graph, strategy_center)
        strategic_lessons = self._strategic_lessons(strategy_center, causal_graph)
        organizational_wisdom = self._organizational_wisdom(governance_lessons, stability_lessons, strategic_lessons)
        memory_clusters = self._memory_clusters(recent_memories, repeated_patterns, correlations)
        critical_memories = [
            item for item in recent_memories
            if item.get("confidence") == "high" or "critical" in item.get("risks", [])
        ]
        status = self._status(repeated_patterns, governance_lessons, stability_lessons)

        return {
            "memory_status": status,
            "recent_memories": recent_memories,
            "critical_memories": critical_memories,
            "repeated_patterns": repeated_patterns,
            "governance_lessons": governance_lessons,
            "stability_lessons": stability_lessons,
            "strategic_lessons": strategic_lessons,
            "organizational_wisdom": organizational_wisdom,
            "memory_clusters": memory_clusters,
            "memory_summary": self._summary(recent_memories, repeated_patterns, organizational_wisdom),
            "recommended_actions": self._recommended_actions(status, repeated_patterns),
        }

    def _runtime_memories(self, events: list[dict], signals: list[dict], causal_graph: dict, strategy: dict) -> list[dict]:
        memories = []
        event_counts = Counter(event.get("event_key") for event in events if event.get("event_key"))
        for key, count in event_counts.most_common(5):
            memories.append(self._memory(
                "event_pattern",
                "Runtime Event Layer",
                f"Observed {key}",
                f"{key} appeared {count} time(s) in recent Runtime events.",
                [key],
                ["critical"] if count >= 3 else ["attention"],
                [],
                "observation only",
                "high" if count >= 3 else "medium",
            ))
        for item in signals[:5]:
            key = item.get("signal_key") or item.get("title") or "runtime_signal"
            memories.append(self._memory(
                "signal_pattern",
                "Runtime Signal Layer",
                f"Signal memory: {key}",
                item.get("summary") or item.get("description") or key,
                [key],
                [item.get("severity") or "warning"],
                [],
                "signal retained for analysis",
                "medium",
            ))
        for item in (causal_graph.get("root_causes") or [])[:3]:
            target = item.get("node_id") or "root_cause"
            memories.append(self._memory(
                "causal_learning",
                "Runtime Causal Layer",
                f"Root cause memory: {target}",
                item.get("summary") or f"{target} is a possible recurring propagation source.",
                [target],
                [item.get("severity") or "warning"],
                [],
                "root cause retained for future diagnosis",
                item.get("confidence") or "medium",
            ))
        for item in (strategy.get("technical_debt_risks") or [])[:3]:
            memories.append(self._memory(
                "strategy_learning",
                "Runtime Strategy Layer",
                item.get("title") or "technical debt",
                item.get("summary") or "",
                [],
                [item.get("severity") or "medium"],
                [],
                "strategy risk retained for roadmap planning",
                "high" if item.get("severity") == "critical" else "medium",
            ))
        return memories

    def _repeated_patterns(self, events: list[dict], signals: list[dict], causal_graph: dict, strategy: dict) -> list[dict]:
        event_counts = Counter(event.get("event_key") for event in events if event.get("event_key"))
        signal_keys = {signal.get("signal_key") for signal in signals if signal.get("signal_key")}
        patterns = []
        if event_counts["JSON_CORRUPTED"] >= 2 or self._has_risk(strategy, "JSON coupling"):
            patterns.append(self._pattern("recurring instability", "critical", "JSON dependency increases recurring Runtime fragility."))
        if event_counts["EXPORT_FAILED"] >= 2 or self._has_risk(strategy, "export bottlenecks"):
            patterns.append(self._pattern("recurring export failure", "high", "Export failures may recur without isolation and permission review."))
        if event_counts["POLICY_GATE_BLOCKED"] or "POLICY_CONFLICT_PATTERN" in signal_keys:
            patterns.append(self._pattern("recurring governance conflict", "critical", "Policy or constitution conflict should be retained as governance memory."))
        if event_counts["TRUST_DECREASED"] or "TRUST_COLLAPSE_RISK" in signal_keys:
            patterns.append(self._pattern("recurring trust collapse", "critical", "Trust collapse risk should constrain future automation expansion."))
        if "EVENT_STORM" in signal_keys or event_counts.total() >= 10:
            patterns.append(self._pattern("recurring event storm", "high", "Event storms amplify noise across signal and correlation layers."))
        if causal_graph.get("critical_paths") and not patterns:
            patterns.append(self._pattern("recurring instability", "high", "Critical causal paths indicate repeated propagation risk."))
        return patterns

    def _governance_lessons(self, events: list[dict], signals: list[dict], strategy: dict) -> list[dict]:
        event_keys = {event.get("event_key") for event in events}
        signal_keys = {signal.get("signal_key") for signal in signals}
        lessons = []
        if "BOUNDARY_RISK" in event_keys or "POLICY_CONFLICT_PATTERN" in signal_keys:
            lessons.append(self._lesson("boundary too weak", "critical", "Boundary checks must precede delegation and automation."))
        if "TRUST_DECREASED" in event_keys or "TRUST_COLLAPSE_RISK" in signal_keys:
            lessons.append(self._lesson("trust without governance dangerous", "critical", "Trust signals are unsafe without policy and constitution gates."))
        lessons.append(self._lesson("policy gate should precede automation", "high", "Policy Gate must remain before any automation roadmap expansion."))
        if self._has_risk(strategy, "Runtime high coupling"):
            lessons.append(self._lesson("governance missing is more dangerous than feature missing", "high", "Governance debt can propagate into release and operational risk."))
        return lessons

    def _stability_lessons(self, events: list[dict], causal_graph: dict, strategy: dict) -> list[dict]:
        event_counts = Counter(event.get("event_key") for event in events if event.get("event_key"))
        lessons = []
        if event_counts.total() >= 5:
            lessons.append(self._lesson("event storms amplify correlation noise", "high", "High event volume makes correlation and signal outputs noisier."))
        if self._has_risk(strategy, "Runtime high coupling") or causal_graph.get("critical_paths"):
            lessons.append(self._lesson("excessive coupling reduces recovery confidence", "critical", "Cross-layer coupling makes rollback and recovery less certain."))
        if event_counts["JSON_CORRUPTED"] or self._has_risk(strategy, "JSON coupling"):
            lessons.append(self._lesson("JSON dependency increases fragility", "critical", "JSON storage and writes are fragile Runtime foundations."))
        return lessons or [self._lesson("stable observation preserves confidence", "medium", "Read-only observation keeps Runtime risk bounded.")]

    def _strategic_lessons(self, strategy: dict, causal_graph: dict) -> list[dict]:
        lessons = [
            self._lesson("stability before automation", "critical", "Automation should expand only after Runtime stability improves."),
            self._lesson("governance before delegation", "critical", "Delegation without governance creates unsafe operational memory."),
            self._lesson("simulation before intervention", "high", "Simulation should precede any manual intervention review."),
        ]
        if causal_graph.get("critical_paths"):
            lessons.append(self._lesson("risk containment before release", "critical", "Risk propagation must be contained before release expansion."))
        return lessons

    def _organizational_wisdom(self, governance: list[dict], stability: list[dict], strategic: list[dict]) -> list[dict]:
        wisdom = [
            self._lesson("不要在低 trust 时扩大自动化", "critical", "Low trust must contract automation scope, not expand it."),
            self._lesson("不要在 unstable runtime 下推进 release", "critical", "Runtime instability should block release expansion until manually reviewed."),
            self._lesson("高 confidence 不代表高 safety", "high", "Confidence measures evidence strength, not governance safety."),
            self._lesson("治理缺失比功能缺失更危险", "critical", "Missing governance can turn normal features into systemic risk."),
        ]
        if any(item.get("severity") == "critical" for item in governance + stability + strategic):
            wisdom.append(self._lesson("先收缩风险，再扩展能力", "critical", "Capability expansion should follow risk contraction."))
        return wisdom

    def _memory_clusters(self, memories: list[dict], patterns: list[dict], correlations: list[dict]) -> list[dict]:
        clusters = []
        if any("JSON" in str(item.get("title") or "") for item in memories) or any("JSON" in str(item.get("summary") or "") for item in patterns):
            clusters.append(self._cluster("JSON instability cluster", "critical", "JSON memories, root causes, and technical debt are clustered."))
        if correlations:
            clusters.append(self._cluster("correlation learning cluster", "medium", f"{len(correlations)} correlation(s) retained for cognitive analysis."))
        if any(item.get("severity") == "critical" for item in patterns):
            clusters.append(self._cluster("governance and stability cluster", "critical", "Critical repeated patterns require organizational memory."))
        return clusters

    @staticmethod
    def _memory(memory_type, layer, title, summary, signals, risks, actions, outcome, confidence) -> dict:
        return {
            "memory_type": memory_type,
            "layer": layer,
            "title": title,
            "summary": summary,
            "signals": list(signals or []),
            "risks": list(risks or []),
            "actions": list(actions or []),
            "outcome": outcome,
            "confidence": confidence,
        }

    @staticmethod
    def _pattern(title: str, severity: str, summary: str) -> dict:
        return {"title": title, "severity": severity, "summary": summary}

    @staticmethod
    def _lesson(title: str, severity: str, summary: str) -> dict:
        return {"title": title, "severity": severity, "summary": summary}

    @staticmethod
    def _cluster(title: str, severity: str, summary: str) -> dict:
        return {"title": title, "severity": severity, "summary": summary}

    @staticmethod
    def _has_risk(strategy: dict, title: str) -> bool:
        return any(item.get("title") == title for item in strategy.get("technical_debt_risks") or [])

    @staticmethod
    def _status(patterns: list[dict], governance: list[dict], stability: list[dict]) -> str:
        critical_patterns = sum(1 for item in patterns if item.get("severity") == "critical")
        critical_governance = sum(1 for item in governance if item.get("severity") == "critical")
        recurring_instability = any(item.get("title") == "recurring instability" for item in patterns)
        if len(patterns) >= 3 or critical_governance >= 2 or (recurring_instability and critical_patterns):
            return "critical"
        if patterns or stability:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(memories: list[dict], patterns: list[dict], wisdom: list[dict]) -> str:
        return (
            f"Generated {len(memories)} Runtime memory item(s), "
            f"{len(patterns)} repeated pattern(s), and {len(wisdom)} organizational wisdom item(s)."
        )

    @staticmethod
    def _recommended_actions(status: str, patterns: list[dict]) -> list[str]:
        actions = ["Keep Runtime memory analysis read-only; do not automatically update governance or SOP."]
        if status == "critical":
            actions.append("Use critical memory patterns for manual governance review before expanding automation.")
        if patterns:
            actions.append("Review repeated patterns as organizational learning, not automatic remediation.")
        return actions
