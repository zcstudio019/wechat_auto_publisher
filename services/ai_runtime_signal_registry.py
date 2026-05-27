"""Runtime signal definitions for read-only signal intelligence."""

RUNTIME_SIGNAL_DEFINITIONS = [
    {
        "signal_key": "REPEATED_WARNINGS",
        "severity": "warning",
        "description": "Same warning event appears repeatedly in sequence.",
        "recommended_action": "Review the repeated warning source manually.",
    },
    {
        "signal_key": "CRITICAL_CLUSTER",
        "severity": "critical",
        "description": "Critical events are clustered in the recent event stream.",
        "recommended_action": "Manually inspect clustered critical event sources.",
    },
    {
        "signal_key": "RECOVERY_LOOP",
        "severity": "warning",
        "description": "Recovered and degraded events are oscillating.",
        "recommended_action": "Check whether recovery is failing to stabilize.",
    },
    {
        "signal_key": "EVENT_STORM",
        "severity": "warning",
        "description": "Recent Runtime event volume is unusually high.",
        "recommended_action": "Manually inspect the event burst before changing operations.",
    },
    {
        "signal_key": "EXPORT_INSTABILITY",
        "severity": "warning",
        "description": "Export failed and recovered events are repeating.",
        "recommended_action": "Review export health and file safety checks manually.",
    },
    {
        "signal_key": "JSON_INSTABILITY",
        "severity": "warning",
        "description": "JSON corrupted events appear repeatedly.",
        "recommended_action": "Review JSON state files and backup health manually.",
    },
    {
        "signal_key": "TRUST_COLLAPSE_RISK",
        "severity": "critical",
        "description": "Trust decreased while boundary risk is also present.",
        "recommended_action": "Manually review governance boundaries and trust signals.",
    },
    {
        "signal_key": "RELEASE_RISK_ESCALATION",
        "severity": "critical",
        "description": "Release is blocked while operations are critical.",
        "recommended_action": "Keep release decisions manual until the critical ops source is reviewed.",
    },
    {
        "signal_key": "OPS_DEGRADATION_PATTERN",
        "severity": "warning",
        "description": "Operations warnings and critical events indicate degradation.",
        "recommended_action": "Manually review operations health trend.",
    },
    {
        "signal_key": "POLICY_CONFLICT_PATTERN",
        "severity": "critical",
        "description": "Policy gate blocking appears with governance risk signals.",
        "recommended_action": "Manually review policy gate and governance constraints.",
    },
]


def get_runtime_signal_definitions() -> list[dict]:
    return [dict(item) for item in RUNTIME_SIGNAL_DEFINITIONS]


def get_runtime_signal_registry() -> dict[str, dict]:
    return {item["signal_key"]: dict(item) for item in RUNTIME_SIGNAL_DEFINITIONS}
