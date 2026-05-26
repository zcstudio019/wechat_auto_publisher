from __future__ import annotations

from services.ai_runtime_executive_digest_service import AIRuntimeExecutiveDigestService


class AIRuntimeExecutiveSummaryService:
    """Read-only adapter for the Runtime executive summary center."""

    @classmethod
    def build_runtime_executive_summary_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        digest = AIRuntimeExecutiveDigestService.build_executive_digest(dashboard)
        status = cls._summary_status(digest.get("digest_status"))

        critical_risks = cls._normalize_items(digest.get("blocked_items") or [], "critical")
        today_key_points = cls._normalize_items(digest.get("must_watch_items") or [], "medium")
        executive_recommendations = [
            digest.get("recommended_action") or "",
            *(digest.get("recommended_actions") or []),
        ]
        executive_recommendations = [item for item in executive_recommendations if item][:5]
        decision_needed = cls._decision_items(status, critical_risks)

        return {
            "executive_summary_status": status,
            "summary": digest.get("summary") or "",
            "top_level_conclusion": digest.get("one_line_summary") or "",
            "health_snapshot": cls._snapshot("health", dashboard.get("summary") or {}),
            "risk_snapshot": cls._snapshot("risk", dashboard.get("summary") or {}),
            "runtime_snapshot": cls._snapshot("runtime", dashboard.get("ai_runtime_trust_center") or dashboard.get("ai_runtime_confidence_center") or {}),
            "ops_snapshot": cls._snapshot("ops", dashboard.get("ai_dashboard_ops_health_center") or {}),
            "export_snapshot": cls._snapshot("export", dashboard.get("ai_dashboard_export_operations_center") or {}),
            "automation_snapshot": cls._snapshot("automation", dashboard.get("ai_autoops_control_tower") or {}),
            "today_key_points": today_key_points,
            "critical_risks": critical_risks,
            "executive_recommendations": executive_recommendations,
            "decision_needed": decision_needed,
            "recommended_actions": digest.get("recommended_actions") or executive_recommendations,
            "digest_compat": digest,
        }

    @staticmethod
    def _summary_status(status: str | None) -> str:
        mapping = {
            "stable": "normal",
            "attention": "attention",
            "warning": "warning",
            "critical": "critical",
        }
        return mapping.get(str(status or "").lower(), "unknown")

    @staticmethod
    def _snapshot(kind: str, source: dict) -> dict:
        source = source or {}
        status = (
            source.get("status")
            or source.get("health_status")
            or source.get("ops_status")
            or source.get("operation_status")
            or source.get("trust_status")
            or source.get("confidence_status")
            or source.get("control_status")
            or source.get("automation_status")
            or "unknown"
        )
        return {
            "type": kind,
            "status": status,
            "summary": source.get("summary") or source.get("trend_summary") or source.get("policy_summary") or "",
            "score": source.get("health_score") or source.get("avg_health_score") or source.get("score") or "",
        }

    @staticmethod
    def _normalize_items(items: list, risk_level: str) -> list[dict]:
        normalized = []
        for item in items:
            if isinstance(item, dict):
                normalized.append({
                    "title": item.get("title") or item.get("name") or item.get("source") or "",
                    "summary": item.get("summary") or item.get("reason") or item.get("message") or "",
                    "source": item.get("source") or item.get("source_module") or "",
                    "risk_level": item.get("risk_level") or risk_level,
                    "status": item.get("status") or "attention",
                })
            else:
                normalized.append({
                    "title": str(item),
                    "summary": str(item),
                    "source": "Runtime",
                    "risk_level": risk_level,
                    "status": "attention",
                })
        return normalized[:5]

    @staticmethod
    def _decision_items(status: str, risks: list[dict]) -> list[dict]:
        if status == "critical":
            return [{
                "title": "Runtime high-risk handling",
                "status": "urgent_decision",
                "summary": "Critical Runtime risk requires manual decision before further action.",
                "risk_level": "critical",
                "recommended_action": "Review Mission Control, Ops Health, and blocked items first.",
            }]
        if risks:
            return [{
                "title": "Runtime risk review",
                "status": "decision_needed",
                "summary": "Blocked or high-risk Runtime items need manual review.",
                "risk_level": risks[0].get("risk_level") or "high",
                "recommended_action": "Review critical risks and decide whether to continue.",
            }]
        return [{
            "title": "Routine observation",
            "status": "no_decision_needed",
            "summary": "No executive decision is required right now.",
            "risk_level": "low",
            "recommended_action": "Keep routine observation.",
        }]

    @classmethod
    def build_runtime_executive_summary_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_runtime_executive_summary_center()
        lines = [
            "\u3010AI Runtime \u9ad8\u5c42\u6458\u8981\u4e2d\u5fc3\u3011",
            f"\u72b6\u6001\uff1a{center.get('executive_summary_status') or '-'}",
            f"\u9876\u5c42\u7ed3\u8bba\uff1a{center.get('top_level_conclusion') or '-'}",
            f"\u6458\u8981\uff1a{center.get('summary') or '-'}",
            "",
            "\u4eca\u65e5\u5173\u952e\u70b9\uff1a",
        ]
        for item in center.get("today_key_points") or []:
            lines.append(f"- {item.get('title')}: {item.get('summary')}")
        lines.append("\u63a8\u8350\u52a8\u4f5c\uff1a")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_runtime_executive_summary_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_runtime_executive_summary_center()
        rows = [{
            "\u5206\u7c7b": "\u9ad8\u5c42\u6458\u8981",
            "\u6807\u9898": "\u9876\u5c42\u7ed3\u8bba",
            "\u72b6\u6001": center.get("executive_summary_status") or "",
            "\u6458\u8981": center.get("top_level_conclusion") or center.get("summary") or "",
            "\u98ce\u9669\u7b49\u7ea7": "",
            "\u662f\u5426\u9700\u8981\u51b3\u7b56": "",
            "\u5efa\u8bae\u52a8\u4f5c": "; ".join(center.get("recommended_actions") or []),
        }]
        for key, category in [
            ("today_key_points", "\u4eca\u65e5\u5173\u952e\u70b9"),
            ("critical_risks", "\u5173\u952e\u98ce\u9669"),
            ("decision_needed", "\u9700\u8981\u51b3\u7b56\u4e8b\u9879"),
        ]:
            for item in center.get(key) or []:
                rows.append({
                    "\u5206\u7c7b": category,
                    "\u6807\u9898": item.get("title") or "",
                    "\u72b6\u6001": item.get("status") or "",
                    "\u6458\u8981": item.get("summary") or "",
                    "\u98ce\u9669\u7b49\u7ea7": item.get("risk_level") or "",
                    "\u662f\u5426\u9700\u8981\u51b3\u7b56": item.get("status") or "",
                    "\u5efa\u8bae\u52a8\u4f5c": item.get("recommended_action") or "",
                })
        return rows
