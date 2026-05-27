"""Read-only Runtime signal intelligence aggregation service."""

from collections import Counter

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_signal_engine import AIRuntimeSignalEngine


class AIRuntimeSignalIntelligenceService:
    """Build a dashboard-ready signal intelligence view from Runtime events."""

    @classmethod
    def build_signal_intelligence(cls, event_bus: AIRuntimeEventBus | None = None) -> dict:
        bus = event_bus or AIRuntimeEventBus()
        events = bus.get_recent_events(limit=100)
        analysis = AIRuntimeSignalEngine().analyze_events(events)
        critical_signals = analysis.get("critical_signals") or []
        warning_signals = analysis.get("warning_signals") or []

        if critical_signals:
            status = "critical"
        elif warning_signals:
            status = "warning"
        else:
            status = "stable"

        return {
            "signal_status": status,
            "signals": analysis.get("signals") or [],
            "critical_signals": critical_signals,
            "warning_signals": warning_signals,
            "signal_clusters": cls._signal_clusters(analysis.get("signals") or []),
            "anomaly_patterns": cls._anomaly_patterns(analysis.get("signals") or []),
            "risk_escalations": cls._risk_escalations(analysis.get("signals") or []),
            "stability_score": cls._stability_score(events, analysis.get("signals") or []),
            "signal_summary": analysis.get("signal_summary") or "",
            "recommended_actions": analysis.get("recommended_actions") or [],
        }

    @staticmethod
    def build_signal_intelligence_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 信号智能中心】",
            f"状态：{center.get('signal_status') or 'stable'}",
            f"稳定性分数：{center.get('stability_score', 0)}",
            f"摘要：{center.get('signal_summary') or ''}",
            "",
            "信号：",
        ]
        for signal in center.get("signals") or []:
            lines.append(f"- {signal.get('signal_key')} [{signal.get('severity')}] {signal.get('risk') or signal.get('description')}")
        if not center.get("signals"):
            lines.append("- 暂无 Runtime 信号。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_signal_intelligence_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 信号智能中心",
            "",
            f"- 状态：{center.get('signal_status') or 'stable'}",
            f"- 稳定性分数：{center.get('stability_score', 0)}",
            f"- 摘要：{center.get('signal_summary') or ''}",
            "",
            "## 信号",
        ]
        for signal in center.get("signals") or []:
            lines.append(f"- `{signal.get('signal_key')}` {signal.get('severity')} - {signal.get('risk') or signal.get('description')}")
        if not center.get("signals"):
            lines.append("- 暂无 Runtime 信号。")
        return "\n".join(lines)

    @staticmethod
    def build_signal_intelligence_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for signal in (center or {}).get("signals") or []:
            rows.append({
                "时间": signal.get("timestamp") or "",
                "信号": signal.get("signal_key") or "",
                "严重级别": signal.get("severity") or "",
                "风险": signal.get("risk") or signal.get("description") or "",
                "建议": signal.get("recommended_action") or "",
            })
        return rows

    @staticmethod
    def _signal_clusters(signals: list[dict]) -> list[dict]:
        counts = Counter(signal.get("severity") or "unknown" for signal in signals)
        return [{"cluster": severity, "count": count} for severity, count in sorted(counts.items())]

    @staticmethod
    def _anomaly_patterns(signals: list[dict]) -> list[dict]:
        anomaly_keys = {"REPEATED_WARNINGS", "CRITICAL_CLUSTER", "RECOVERY_LOOP", "EVENT_STORM"}
        return [signal for signal in signals if signal.get("signal_key") in anomaly_keys]

    @staticmethod
    def _risk_escalations(signals: list[dict]) -> list[dict]:
        risk_keys = {"TRUST_COLLAPSE_RISK", "RELEASE_RISK_ESCALATION", "OPS_DEGRADATION_PATTERN", "POLICY_CONFLICT_PATTERN"}
        return [signal for signal in signals if signal.get("signal_key") in risk_keys]

    @staticmethod
    def _stability_score(events: list[dict], signals: list[dict]) -> int:
        critical_events = len([event for event in events if event.get("severity") == "critical"])
        warning_events = len([event for event in events if event.get("severity") == "warning"])
        recovery_events = len([
            event for event in events
            if str(event.get("event_key") or "").endswith("_RECOVERED") or event.get("event_key") == "RELEASE_READY"
        ])
        critical_signals = len([signal for signal in signals if signal.get("severity") == "critical"])
        warning_signals = len([signal for signal in signals if signal.get("severity") == "warning"])
        event_storm = any(signal.get("signal_key") == "EVENT_STORM" for signal in signals)

        score = 100
        score -= critical_events * 10
        score -= warning_events * 4
        score -= critical_signals * 15
        score -= warning_signals * 7
        if event_storm:
            score -= 15
        score += min(recovery_events * 3, 15)
        return max(0, min(100, score))
