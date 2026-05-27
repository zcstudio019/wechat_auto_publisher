"""Runtime event definitions for the read-only AI Runtime OS event layer."""

RUNTIME_EVENT_DEFINITIONS = [
    {
        "event_key": "RUNTIME_DEGRADED",
        "severity": "warning",
        "layer": "L5 Runtime Layer",
        "description": "Runtime kernel status degraded from healthy state.",
    },
    {
        "event_key": "RUNTIME_RECOVERED",
        "severity": "info",
        "layer": "L5 Runtime Layer",
        "description": "Runtime kernel status recovered to healthy state.",
    },
    {
        "event_key": "OPS_WARNING",
        "severity": "warning",
        "layer": "L4 Operations Layer",
        "description": "Operations health center reported warning status.",
    },
    {
        "event_key": "OPS_CRITICAL",
        "severity": "critical",
        "layer": "L4 Operations Layer",
        "description": "Operations health center reported critical status.",
    },
    {
        "event_key": "SMOKE_TEST_FAILED",
        "severity": "critical",
        "layer": "L7 Diagnostics Layer",
        "description": "Dashboard smoke test reported failed status.",
    },
    {
        "event_key": "SMOKE_TEST_RECOVERED",
        "severity": "info",
        "layer": "L7 Diagnostics Layer",
        "description": "Dashboard smoke test recovered to passing status.",
    },
    {
        "event_key": "EXPORT_FAILED",
        "severity": "warning",
        "layer": "L8 Export / Documentation Layer",
        "description": "Export operations reported failed status.",
    },
    {
        "event_key": "EXPORT_RECOVERED",
        "severity": "info",
        "layer": "L8 Export / Documentation Layer",
        "description": "Export operations recovered to normal status.",
    },
    {
        "event_key": "JSON_CORRUPTED",
        "severity": "warning",
        "layer": "L7 Diagnostics Layer",
        "description": "Runtime JSON state appears corrupted or unreadable.",
    },
    {
        "event_key": "JSON_RECOVERED",
        "severity": "info",
        "layer": "L7 Diagnostics Layer",
        "description": "Runtime JSON state recovered to readable status.",
    },
    {
        "event_key": "RELEASE_BLOCKED",
        "severity": "critical",
        "layer": "L9 Release Layer",
        "description": "Release readiness reported blocked status.",
    },
    {
        "event_key": "RELEASE_READY",
        "severity": "info",
        "layer": "L9 Release Layer",
        "description": "Release readiness reported ready status.",
    },
    {
        "event_key": "TRUST_DECREASED",
        "severity": "warning",
        "layer": "L6 Governance Layer",
        "description": "Runtime trust signal decreased or entered warning status.",
    },
    {
        "event_key": "TRUST_RECOVERED",
        "severity": "info",
        "layer": "L6 Governance Layer",
        "description": "Runtime trust signal recovered to normal status.",
    },
    {
        "event_key": "BOUNDARY_RISK",
        "severity": "warning",
        "layer": "L6 Governance Layer",
        "description": "Runtime boundary center reported boundary risk.",
    },
    {
        "event_key": "POLICY_GATE_BLOCKED",
        "severity": "critical",
        "layer": "L6 Governance Layer",
        "description": "Runtime policy gate reported blocked status.",
    },
]


def get_runtime_event_definitions() -> list[dict]:
    return [dict(item) for item in RUNTIME_EVENT_DEFINITIONS]


def get_runtime_event_registry() -> dict[str, dict]:
    return {item["event_key"]: dict(item) for item in RUNTIME_EVENT_DEFINITIONS}
