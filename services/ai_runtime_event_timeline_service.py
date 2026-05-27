"""Read-only Runtime event timeline aggregation service."""

from collections import Counter

from services.ai_runtime_event_bus import AIRuntimeEventBus


class AIRuntimeEventTimelineService:
    """Build a dashboard-friendly view over recent Runtime events."""

    @classmethod
    def build_event_timeline(cls, event_bus: AIRuntimeEventBus | None = None) -> dict:
        bus = event_bus or AIRuntimeEventBus()
        recent_events = bus.get_recent_events(limit=50)
        critical_events = [event for event in recent_events if event.get("severity") == "critical"]
        warning_events = [event for event in recent_events if event.get("severity") == "warning"]
        layer_distribution = cls._layer_distribution(recent_events)

        if critical_events:
            status = "critical"
        elif warning_events:
            status = "warning"
        else:
            status = "stable"

        return {
            "timeline_status": status,
            "recent_events": recent_events,
            "critical_events": critical_events,
            "warning_events": warning_events,
            "layer_distribution": layer_distribution,
            "event_summary": cls._summary(status, recent_events, critical_events, warning_events),
            "recommended_actions": cls._recommended_actions(status),
        }

    @staticmethod
    def build_event_timeline_text(timeline: dict | None = None) -> str:
        timeline = timeline or {}
        lines = [
            "【AI Runtime 事件时间线】",
            f"状态：{timeline.get('timeline_status') or 'stable'}",
            f"摘要：{timeline.get('event_summary') or ''}",
            "",
            "最近事件：",
        ]
        for event in (timeline.get("recent_events") or [])[:20]:
            lines.append(
                f"- {event.get('timestamp', '')} {event.get('event_key', '')} "
                f"[{event.get('severity', '')}] {event.get('layer', '')}"
            )
        if not timeline.get("recent_events"):
            lines.append("- 暂无 Runtime 事件。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (timeline.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_event_timeline_markdown(timeline: dict | None = None) -> str:
        timeline = timeline or {}
        lines = [
            "# AI Runtime 事件时间线",
            "",
            f"- 状态：{timeline.get('timeline_status') or 'stable'}",
            f"- 摘要：{timeline.get('event_summary') or ''}",
            "",
            "## 最近事件",
        ]
        for event in (timeline.get("recent_events") or [])[:20]:
            lines.append(
                f"- `{event.get('timestamp', '')}` `{event.get('event_key', '')}` "
                f"{event.get('severity', '')} / {event.get('layer', '')}"
            )
        if not timeline.get("recent_events"):
            lines.append("- 暂无 Runtime 事件。")
        return "\n".join(lines)

    @staticmethod
    def build_event_timeline_rows(timeline: dict | None = None) -> list[dict]:
        rows = []
        for event in (timeline or {}).get("recent_events") or []:
            rows.append({
                "时间": event.get("timestamp") or "",
                "事件": event.get("event_key") or "",
                "严重级别": event.get("severity") or "",
                "Layer": event.get("layer") or "",
                "摘要": event.get("description") or "",
            })
        return rows

    @staticmethod
    def _layer_distribution(events: list[dict]) -> list[dict]:
        counts = Counter(event.get("layer") or "unknown" for event in events)
        return [
            {"layer": layer, "count": count}
            for layer, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    @staticmethod
    def _summary(status: str, recent_events: list[dict], critical_events: list[dict], warning_events: list[dict]) -> str:
        if status == "critical":
            return f"最近 {len(recent_events)} 条 Runtime 事件中有 {len(critical_events)} 条 critical。"
        if status == "warning":
            return f"最近 {len(recent_events)} 条 Runtime 事件中有 {len(warning_events)} 条 warning。"
        return f"最近 {len(recent_events)} 条 Runtime 事件未发现 critical 或 warning。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["保持事件只读记录，人工查看 critical 事件来源。"]
        if status == "warning":
            return ["保持事件只读记录，人工观察 warning 事件趋势。"]
        return ["保持事件时间线只读观察，不自动执行任何动作。"]
