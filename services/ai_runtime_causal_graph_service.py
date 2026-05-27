"""Dashboard service for the read-only AI Runtime causal graph center."""

from services.ai_runtime_causal_graph_engine import AIRuntimeCausalGraphEngine
from services.ai_runtime_correlation_service import AIRuntimeCorrelationService
from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService


class AIRuntimeCausalGraphService:
    """Build and export a read-only Runtime causal graph center."""

    @classmethod
    def build_causal_graph_center(cls, event_bus: AIRuntimeEventBus | None = None) -> dict:
        bus = event_bus or AIRuntimeEventBus()
        events = bus.get_recent_events(limit=100)
        signal_center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(bus)
        correlation_center = AIRuntimeCorrelationService.build_correlation_center(bus)
        graph = AIRuntimeCausalGraphEngine().build_graph(
            events,
            signal_center.get("signals") or [],
            correlation_center.get("correlations") or [],
        )
        status = cls._status(graph)

        return {
            "causal_status": status,
            "nodes": graph.get("nodes") or [],
            "edges": graph.get("edges") or [],
            "root_causes": graph.get("root_causes") or [],
            "symptoms": graph.get("symptoms") or [],
            "fragile_nodes": graph.get("fragile_nodes") or [],
            "critical_paths": graph.get("critical_paths") or [],
            "causal_summary": graph.get("causal_summary") or "",
            "recommended_actions": graph.get("recommended_actions") or [],
        }

    @staticmethod
    def build_causal_graph_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 因果图谱中心】",
            f"状态：{center.get('causal_status') or 'stable'}",
            f"摘要：{center.get('causal_summary') or ''}",
            "",
            "因果边：",
        ]
        for item in center.get("edges") or []:
            lines.append(
                f"- {item.get('source')} -> {item.get('target')} "
                f"[{item.get('relationship')}/{item.get('confidence')}] {item.get('summary')}"
            )
        if not center.get("edges"):
            lines.append("- 暂无 Runtime 因果边。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_causal_graph_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 因果图谱中心",
            "",
            f"- 状态：{center.get('causal_status') or 'stable'}",
            f"- 摘要：{center.get('causal_summary') or ''}",
            "",
            "## 因果边",
        ]
        for item in center.get("edges") or []:
            lines.append(
                f"- `{item.get('source')}` -> `{item.get('target')}` "
                f"{item.get('relationship')} / {item.get('confidence')}: {item.get('summary')}"
            )
        if not center.get("edges"):
            lines.append("- 暂无 Runtime 因果边。")
        return "\n".join(lines)

    @staticmethod
    def build_causal_graph_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in (center or {}).get("edges") or []:
            rows.append({
                "来源": item.get("source") or "",
                "目标": item.get("target") or "",
                "关系": item.get("relationship") or "",
                "置信度": item.get("confidence") or "",
                "摘要": item.get("summary") or "",
            })
        return rows

    @staticmethod
    def _status(graph: dict) -> str:
        high_root = any(
            item.get("confidence") == "high"
            for item in graph.get("root_causes") or []
        )
        critical_path = any(
            item.get("severity") == "critical"
            for item in graph.get("critical_paths") or []
        )
        if high_root or critical_path:
            return "critical"
        if graph.get("root_causes") or graph.get("fragile_nodes") or graph.get("edges"):
            return "warning"
        return "stable"
