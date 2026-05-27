"""Read-only Runtime correlation center service."""

from services.ai_runtime_correlation_engine import AIRuntimeCorrelationEngine
from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService


class AIRuntimeCorrelationService:
    """Build a dashboard-ready Runtime correlation center."""

    @classmethod
    def build_correlation_center(cls, event_bus: AIRuntimeEventBus | None = None) -> dict:
        bus = event_bus or AIRuntimeEventBus()
        events = bus.get_recent_events(limit=100)
        signal_center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(bus)
        analysis = AIRuntimeCorrelationEngine().analyze(events, signal_center.get("signals") or [])
        status = cls._status(analysis)

        return {
            "correlation_status": status,
            "correlations": analysis.get("correlations") or [],
            "root_cause_candidates": analysis.get("root_cause_candidates") or [],
            "co_occurrence_patterns": analysis.get("co_occurrence_patterns") or [],
            "impact_chains": analysis.get("impact_chains") or [],
            "correlation_summary": analysis.get("correlation_summary") or "",
            "recommended_actions": analysis.get("recommended_actions") or [],
        }

    @staticmethod
    def build_correlation_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 关联分析中心】",
            f"状态：{center.get('correlation_status') or 'stable'}",
            f"摘要：{center.get('correlation_summary') or ''}",
            "",
            "关联：",
        ]
        for item in center.get("correlations") or []:
            lines.append(
                f"- {item.get('source')} -> {item.get('target')} "
                f"[{item.get('correlation_type')}/{item.get('confidence')}] {item.get('summary')}"
            )
        if not center.get("correlations"):
            lines.append("- 暂无 Runtime 关联风险。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_correlation_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 关联分析中心",
            "",
            f"- 状态：{center.get('correlation_status') or 'stable'}",
            f"- 摘要：{center.get('correlation_summary') or ''}",
            "",
            "## 关联",
        ]
        for item in center.get("correlations") or []:
            lines.append(
                f"- `{item.get('source')}` -> `{item.get('target')}` "
                f"{item.get('correlation_type')} / {item.get('confidence')}: {item.get('summary')}"
            )
        if not center.get("correlations"):
            lines.append("- 暂无 Runtime 关联风险。")
        return "\n".join(lines)

    @staticmethod
    def build_correlation_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in (center or {}).get("correlations") or []:
            rows.append({
                "来源": item.get("source") or "",
                "目标": item.get("target") or "",
                "类型": item.get("correlation_type") or "",
                "置信度": item.get("confidence") or "",
                "摘要": item.get("summary") or "",
            })
        return rows

    @staticmethod
    def _status(analysis: dict) -> str:
        high_root = any(
            item.get("confidence") == "high"
            for item in analysis.get("root_cause_candidates") or []
        )
        critical_chain = any(
            item.get("severity") == "critical"
            for item in analysis.get("impact_chains") or []
        )
        if high_root or critical_chain:
            return "critical"

        medium_correlation = any(
            item.get("confidence") == "medium"
            for item in analysis.get("correlations") or []
        )
        if medium_correlation:
            return "attention"
        return "stable"
