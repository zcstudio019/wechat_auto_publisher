"""Read-only Phase-3 batch approval insight center."""

from datetime import datetime, timezone

from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore


class AIRuntimeBatchApprovalInsightService:
    """Analyze approval queue shape without changing approvals."""

    @classmethod
    def build_batch_approval_insight(cls, dashboard: dict | None = None, store: AIRuntimeActionApprovalStore | None = None) -> dict:
        store = store or AIRuntimeActionApprovalStore()
        approvals = store.read_approvals()
        pending = [item for item in approvals if item.get("status") == "pending"]
        grouped_by_source = cls._group(pending, "source")
        grouped_by_risk = cls._group(pending, "risk_level")
        aging = [item for item in pending if cls._age_days(item.get("created_at")) >= 7]
        high_risk = [item for item in pending if str(item.get("risk_level") or "").lower() in {"high", "critical", "forbidden", "blocked"}]
        bottlenecks = cls._bottlenecks(grouped_by_source, grouped_by_risk, high_risk, aging)
        recommendations = cls._recommendations(pending, high_risk, aging)
        status = cls._status(pending, high_risk, aging)
        return {
            "insight_status": status,
            "summary": f"当前 pending 审批 {len(pending)} 条，高风险 {len(high_risk)} 条，超期 {len(aging)} 条。",
            "pending_count": len(pending),
            "grouped_by_source": grouped_by_source,
            "grouped_by_risk": grouped_by_risk,
            "aging_pending": aging[:8],
            "high_risk_pending": high_risk[:8],
            "approval_bottlenecks": bottlenecks[:8],
            "batch_recommendations": recommendations[:8],
            "recommended_actions": recommendations[:5],
        }

    @classmethod
    def build_batch_approval_insight_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["【AI Runtime 批量审批洞察中心】", f"状态：{center.get('insight_status') or 'normal'}", center.get("summary") or "", ""]
        for title, key in cls._sections():
            lines.append(f"{title}：")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_batch_approval_insight_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["# AI Runtime 批量审批洞察中心", "", f"- 状态：{center.get('insight_status') or 'normal'}", f"- 摘要：{center.get('summary') or ''}", ""]
        for title, key in cls._sections():
            lines.append(f"## {title}")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_batch_approval_insight_rows(cls, center: dict | None = None) -> list[dict]:
        rows = []
        for title, key in cls._sections():
            for item in (center or {}).get(key) or []:
                rows.append({
                    "维度": title,
                    "数量": item.get("count") or "",
                    "风险": item.get("risk_level") or item.get("risk") or "",
                    "来源": item.get("source") or item.get("key") or "",
                    "建议": item.get("summary") or item.get("title") or "",
                })
        return rows

    @staticmethod
    def _group(items: list[dict], key: str) -> list[dict]:
        counts = {}
        for item in items:
            name = str(item.get(key) or "unknown")
            counts[name] = counts.get(name, 0) + 1
        return [{"key": name, "count": count} for name, count in sorted(counts.items())]

    @staticmethod
    def _age_days(created_at: str | None) -> int:
        if not created_at:
            return 0
        try:
            parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max((datetime.now(timezone.utc) - parsed).days, 0)
        except ValueError:
            return 0

    @staticmethod
    def _bottlenecks(source_groups: list[dict], risk_groups: list[dict], high_risk: list[dict], aging: list[dict]) -> list[dict]:
        bottlenecks = []
        for group in source_groups:
            if group.get("count", 0) >= 3:
                bottlenecks.append({"title": f"{group.get('key')} pending 审批集中", "count": group.get("count"), "source": group.get("key"), "summary": "建议分批人工复核。"})
        for group in risk_groups:
            if str(group.get("key")).lower() in {"high", "critical", "forbidden", "blocked"}:
                bottlenecks.append({"title": f"{group.get('key')} 风险审批堆积", "count": group.get("count"), "risk": group.get("key"), "summary": "必须保持人工审批。"})
        if aging:
            bottlenecks.append({"title": "存在超期 pending 审批", "count": len(aging), "risk": "attention", "summary": "建议人工清理审批队列。"})
        if high_risk:
            bottlenecks.append({"title": "存在高风险 pending 审批", "count": len(high_risk), "risk": "high", "summary": "优先由治理负责人查看。"})
        return bottlenecks

    @staticmethod
    def _recommendations(pending: list[dict], high_risk: list[dict], aging: list[dict]) -> list[dict]:
        if not pending:
            return [{"title": "当前无 pending 审批", "summary": "维持常规巡检。"}]
        items = [{"title": "按风险分组进行人工审批", "summary": "先看 high/critical，再看普通 pending。"}]
        if high_risk:
            items.append({"title": "高风险审批必须人工复核", "summary": "不允许自动批准或自动处理。"})
        if aging:
            items.append({"title": "清理超期审批", "summary": "仅更新审批记录，不处理业务动作。"})
        return items

    @staticmethod
    def _status(pending: list[dict], high_risk: list[dict], aging: list[dict]) -> str:
        if any(str(item.get("risk_level") or "").lower() in {"critical", "forbidden", "blocked"} for item in pending) or aging:
            return "blocked"
        if high_risk or len(pending) >= 3:
            return "attention"
        return "normal"

    @staticmethod
    def _format_item(item: dict) -> str:
        return f"- {item.get('title') or item.get('key') or ''} / {item.get('count') or ''} / {item.get('summary') or item.get('risk') or ''}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("按来源分组", "grouped_by_source"),
            ("按风险分组", "grouped_by_risk"),
            ("超期审批", "aging_pending"),
            ("高风险审批", "high_risk_pending"),
            ("审批瓶颈", "approval_bottlenecks"),
        ]
