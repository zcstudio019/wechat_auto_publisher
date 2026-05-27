"""Dashboard service for the read-only AI Runtime memory center."""

from services.ai_runtime_correlation_service import AIRuntimeCorrelationService
from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_memory_engine import AIRuntimeMemoryEngine
from services.ai_runtime_memory_store import AIRuntimeMemoryStore
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeMemoryService:
    """Build and export cognitive Runtime memory analysis."""

    @classmethod
    def build_memory_center(
        cls,
        dashboard: dict | None = None,
        memory_store: AIRuntimeMemoryStore | None = None,
        event_bus: AIRuntimeEventBus | None = None,
    ) -> dict:
        dashboard = dashboard or {}
        store = memory_store or AIRuntimeMemoryStore()
        bus = event_bus or AIRuntimeEventBus()
        signal_center = dashboard.get("ai_runtime_signal_intelligence")
        if not signal_center:
            signal_center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(bus)
        correlation_center = dashboard.get("ai_runtime_correlation_center")
        if not correlation_center:
            correlation_center = AIRuntimeCorrelationService.build_correlation_center(bus)
        strategy_center = dashboard.get("ai_runtime_strategy_center")
        if not strategy_center:
            strategy_center = AIRuntimeStrategyService.build_strategy_center(dashboard)

        result = AIRuntimeMemoryEngine().build_memory(
            bus.get_recent_events(limit=100),
            signal_center.get("signals") or [],
            correlation_center.get("correlations") or [],
            dashboard.get("ai_runtime_causal_graph_center") or {},
            strategy_center,
        )
        stored_recent = store.recent_memories(limit=20)
        recent_memories = stored_recent + (result.get("recent_memories") or [])

        return {
            "memory_status": result.get("memory_status") or "stable",
            "recent_memories": recent_memories[:50],
            "critical_memories": (result.get("critical_memories") or []) + [
                item for item in stored_recent
                if item.get("confidence") == "high" or "critical" in (item.get("risks") or [])
            ],
            "repeated_patterns": result.get("repeated_patterns") or [],
            "governance_lessons": result.get("governance_lessons") or [],
            "stability_lessons": result.get("stability_lessons") or [],
            "strategic_lessons": result.get("strategic_lessons") or [],
            "organizational_wisdom": result.get("organizational_wisdom") or [],
            "memory_clusters": result.get("memory_clusters") or [],
            "memory_summary": result.get("memory_summary") or "",
            "recommended_actions": result.get("recommended_actions") or [],
        }

    @staticmethod
    def build_memory_text(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 记忆中心】",
            f"状态：{center.get('memory_status') or 'stable'}",
            f"摘要：{center.get('memory_summary') or ''}",
            "",
            "记忆：",
        ]
        for item in AIRuntimeMemoryService._memory_items(center):
            lines.append(
                f"- {item.get('title')} / {item.get('type')} / "
                f"{item.get('risk')} / {item.get('outcome')} / {item.get('summary')}"
            )
        if not AIRuntimeMemoryService._memory_items(center):
            lines.append("- 暂无 Runtime 认知记忆。")
        lines.extend(["", "建议："])
        lines.extend([f"- {item}" for item in (center.get("recommended_actions") or [])])
        return "\n".join(lines)

    @staticmethod
    def build_memory_markdown(center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 记忆中心",
            "",
            f"- 状态：{center.get('memory_status') or 'stable'}",
            f"- 摘要：{center.get('memory_summary') or ''}",
            "",
            "## 认知记忆",
        ]
        for item in AIRuntimeMemoryService._memory_items(center):
            lines.append(
                f"- `{item.get('title')}` {item.get('type')} / "
                f"{item.get('risk')}: {item.get('summary')}"
            )
        if not AIRuntimeMemoryService._memory_items(center):
            lines.append("- 暂无 Runtime 认知记忆。")
        return "\n".join(lines)

    @staticmethod
    def build_memory_rows(center: dict | None = None) -> list[dict]:
        rows = []
        for item in AIRuntimeMemoryService._memory_items(center or {}):
            rows.append({
                "记忆": item.get("title") or "",
                "类型": item.get("type") or "",
                "风险": item.get("risk") or "",
                "结论": item.get("outcome") or "",
                "建议": item.get("summary") or "",
            })
        return rows

    @staticmethod
    def _memory_items(center: dict) -> list[dict]:
        items = []
        for item in center.get("recent_memories") or []:
            items.append({
                "title": item.get("title") or "",
                "type": item.get("memory_type") or "memory",
                "risk": ", ".join(str(value) for value in (item.get("risks") or [])),
                "outcome": item.get("outcome") or "",
                "summary": item.get("summary") or "",
            })
        for key, item_type in [
            ("repeated_patterns", "pattern"),
            ("governance_lessons", "governance_lesson"),
            ("stability_lessons", "stability_lesson"),
            ("strategic_lessons", "strategic_lesson"),
            ("organizational_wisdom", "wisdom"),
            ("memory_clusters", "cluster"),
        ]:
            for item in center.get(key) or []:
                items.append({
                    "title": item.get("title") or "",
                    "type": item_type,
                    "risk": item.get("severity") or "",
                    "outcome": "read-only lesson",
                    "summary": item.get("summary") or "",
                })
        return items
