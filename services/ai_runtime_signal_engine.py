"""Read-only signal analysis engine for Runtime events."""

from collections import Counter

from services.ai_runtime_signal_registry import get_runtime_signal_registry


class AIRuntimeSignalEngine:
    """Detect signal patterns from Runtime events without executing actions."""

    EVENT_STORM_THRESHOLD = 20
    CRITICAL_CLUSTER_THRESHOLD = 3
    REPEATED_WARNING_THRESHOLD = 3

    def __init__(self):
        self.registry = get_runtime_signal_registry()

    def analyze_events(self, events):
        events = [event for event in (events or []) if isinstance(event, dict)]
        signals = []

        self._detect_repeated_warnings(events, signals)
        self._detect_critical_cluster(events, signals)
        self._detect_recovery_loop(events, signals)
        self._detect_event_storm(events, signals)
        self._detect_export_instability(events, signals)
        self._detect_json_instability(events, signals)
        self._detect_trust_collapse(events, signals)
        self._detect_release_escalation(events, signals)
        self._detect_ops_degradation(events, signals)
        self._detect_policy_conflict(events, signals)

        signals = self._dedupe_signals(signals)
        critical_signals = [signal for signal in signals if signal.get("severity") == "critical"]
        warning_signals = [signal for signal in signals if signal.get("severity") == "warning"]

        return {
            "signals": signals,
            "critical_signals": critical_signals,
            "warning_signals": warning_signals,
            "signal_summary": self._summary(signals, critical_signals, warning_signals),
            "recommended_actions": self._recommended_actions(signals),
        }

    def _add_signal(self, signals, signal_key, evidence=None):
        definition = self.registry.get(signal_key) or {
            "signal_key": signal_key,
            "severity": "warning",
            "description": "Unregistered Runtime signal.",
            "recommended_action": "Review Runtime signal manually.",
        }
        signals.append({
            "signal_key": signal_key,
            "severity": definition.get("severity") or "warning",
            "description": definition.get("description") or "",
            "recommended_action": definition.get("recommended_action") or "",
            "risk": evidence or "",
        })

    def _detect_repeated_warnings(self, events, signals):
        current_key = None
        run_length = 0
        for event in events:
            if event.get("severity") == "warning":
                event_key = event.get("event_key")
                if event_key == current_key:
                    run_length += 1
                else:
                    current_key = event_key
                    run_length = 1
                if run_length >= self.REPEATED_WARNING_THRESHOLD:
                    self._add_signal(signals, "REPEATED_WARNINGS", f"{event_key} repeated {run_length} times")
                    return
            else:
                current_key = None
                run_length = 0

    def _detect_critical_cluster(self, events, signals):
        critical_count = len([event for event in events[:10] if event.get("severity") == "critical"])
        if critical_count >= self.CRITICAL_CLUSTER_THRESHOLD:
            self._add_signal(signals, "CRITICAL_CLUSTER", f"{critical_count} critical events in recent window")

    def _detect_recovery_loop(self, events, signals):
        keys = [event.get("event_key") for event in events]
        degraded = keys.count("RUNTIME_DEGRADED")
        recovered = keys.count("RUNTIME_RECOVERED")
        if degraded >= 2 and recovered >= 2:
            self._add_signal(signals, "RECOVERY_LOOP", "runtime degraded/recovered oscillation")

    def _detect_event_storm(self, events, signals):
        if len(events) >= self.EVENT_STORM_THRESHOLD:
            self._add_signal(signals, "EVENT_STORM", f"{len(events)} events in recent window")

    def _detect_export_instability(self, events, signals):
        keys = [event.get("event_key") for event in events]
        if keys.count("EXPORT_FAILED") >= 2 and keys.count("EXPORT_RECOVERED") >= 2:
            self._add_signal(signals, "EXPORT_INSTABILITY", "export failed/recovered repeated")

    def _detect_json_instability(self, events, signals):
        keys = [event.get("event_key") for event in events]
        if keys.count("JSON_CORRUPTED") >= 2:
            self._add_signal(signals, "JSON_INSTABILITY", "JSON_CORRUPTED repeated")

    def _detect_trust_collapse(self, events, signals):
        keys = {event.get("event_key") for event in events}
        if "TRUST_DECREASED" in keys and "BOUNDARY_RISK" in keys:
            self._add_signal(signals, "TRUST_COLLAPSE_RISK", "trust decreased with boundary risk")

    def _detect_release_escalation(self, events, signals):
        keys = {event.get("event_key") for event in events}
        if "RELEASE_BLOCKED" in keys and "OPS_CRITICAL" in keys:
            self._add_signal(signals, "RELEASE_RISK_ESCALATION", "release blocked with ops critical")

    def _detect_ops_degradation(self, events, signals):
        keys = [event.get("event_key") for event in events]
        if keys.count("OPS_WARNING") >= 3 or ("OPS_CRITICAL" in keys and "OPS_WARNING" in keys):
            self._add_signal(signals, "OPS_DEGRADATION_PATTERN", "ops warning/critical pattern")

    def _detect_policy_conflict(self, events, signals):
        keys = {event.get("event_key") for event in events}
        if "POLICY_GATE_BLOCKED" in keys and ({"BOUNDARY_RISK", "TRUST_DECREASED"} & keys):
            self._add_signal(signals, "POLICY_CONFLICT_PATTERN", "policy gate blocked with governance risk")

    @staticmethod
    def _dedupe_signals(signals):
        seen = set()
        result = []
        for signal in signals:
            key = signal.get("signal_key")
            if key in seen:
                continue
            seen.add(key)
            result.append(signal)
        return result

    @staticmethod
    def _summary(signals, critical_signals, warning_signals):
        if critical_signals:
            return f"Detected {len(critical_signals)} critical Runtime signals and {len(warning_signals)} warning signals."
        if warning_signals:
            return f"Detected {len(warning_signals)} warning Runtime signals."
        return "No Runtime anomaly signal detected in the recent event window."

    @staticmethod
    def _recommended_actions(signals):
        actions = []
        for signal in signals:
            action = signal.get("recommended_action")
            if action and action not in actions:
                actions.append(action)
        return actions or ["Keep Runtime signal intelligence read-only and continue manual observation."]

    @staticmethod
    def event_counts(events):
        return Counter(event.get("event_key") for event in events or [])
