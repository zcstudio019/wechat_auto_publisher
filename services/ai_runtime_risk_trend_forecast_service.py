"""Read-only Phase-3 risk trend forecast center."""


class AIRuntimeRiskTrendForecastService:
    """Forecast trend signals from existing risk and signal centers."""

    @classmethod
    def build_risk_trend_forecast(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        risks = cls._collect_risks(dashboard)
        rising = [item for item in risks if cls._trend(item) == "rising"]
        stable = [item for item in risks if cls._trend(item) == "stable"]
        declining = [item for item in risks if cls._trend(item) == "declining"]
        forecast_items = cls._forecast_items(rising, stable, declining)
        critical_forecasts = [item for item in forecast_items if item.get("risk_level") in {"critical", "high"}]
        status = "critical" if any(item.get("risk_level") == "critical" for item in forecast_items) else "warning" if rising else "stable"
        return {
            "forecast_status": status,
            "summary": cls._summary(status, rising, declining),
            "rising_risks": rising[:8],
            "stable_risks": stable[:8],
            "declining_risks": declining[:8],
            "forecast_items": forecast_items[:10],
            "critical_forecasts": critical_forecasts[:8],
            "next_period_watchlist": (rising + stable)[:8],
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_risk_trend_forecast_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["【AI Runtime 风险趋势预测中心】", f"状态：{center.get('forecast_status') or 'stable'}", center.get("summary") or "", ""]
        for title, key in cls._sections():
            lines.append(f"{title}：")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_risk_trend_forecast_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["# AI Runtime 风险趋势预测中心", "", f"- 状态：{center.get('forecast_status') or 'stable'}", f"- 摘要：{center.get('summary') or ''}", ""]
        for title, key in cls._sections():
            lines.append(f"## {title}")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_risk_trend_forecast_rows(cls, center: dict | None = None) -> list[dict]:
        rows = []
        for title, key in cls._sections():
            for item in (center or {}).get(key) or []:
                rows.append({
                    "风险": item.get("title") or item.get("summary") or "",
                    "趋势": item.get("trend") or "",
                    "来源": item.get("source") or "",
                    "预测": item.get("forecast") or item.get("summary") or "",
                    "建议": item.get("suggestion") or "",
                })
        return rows

    @classmethod
    def _collect_risks(cls, dashboard: dict) -> list[dict]:
        event = dashboard.get("ai_runtime_event_timeline") or {}
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        monthly = dashboard.get("ai_runtime_monthly_board_report") or {}
        approval = dashboard.get("ai_runtime_action_approval_center") or {}
        plan = dashboard.get("ai_runtime_execution_plan_center") or {}
        risks = []
        for items, source in [
            (event.get("critical_events") or event.get("warning_events"), "Event Timeline"),
            (signal.get("critical_signals") or signal.get("warning_signals"), "Signal Intelligence"),
            (weekly.get("top_risks"), "Weekly Executive"),
            (monthly.get("strategic_threats"), "Monthly Board"),
            (approval.get("high_risk_pending"), "Action Approval"),
            (plan.get("high_risk_plans"), "Execution Plan"),
        ]:
            risks += cls._items(items, source)
        return risks

    @staticmethod
    def _items(items, source: str) -> list[dict]:
        normalized = []
        for item in items or []:
            copied = dict(item) if isinstance(item, dict) else {"title": str(item)}
            copied.setdefault("source", source)
            copied["trend"] = AIRuntimeRiskTrendForecastService._trend(copied)
            normalized.append(copied)
        return normalized

    @staticmethod
    def _trend(item: dict) -> str:
        text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "status", "risk", "risk_level", "severity", "trend")).lower()
        if any(token in text for token in ("recovered", "resolved", "healthy", "passed", "declining", "decrease")):
            return "declining"
        if any(token in text for token in ("critical", "high", "blocked", "forbidden", "rising", "increase", "escalation", "storm")):
            return "rising"
        return "stable"

    @staticmethod
    def _forecast_items(rising: list[dict], stable: list[dict], declining: list[dict]) -> list[dict]:
        items = []
        for item in rising:
            risk_level = "critical" if "critical" in " ".join(str(v).lower() for v in item.values()) else "high"
            items.append({**item, "risk_level": risk_level, "forecast": "下周期可能继续扩散，需要人工观察。"})
        for item in stable[:3]:
            items.append({**item, "risk_level": "medium", "forecast": "风险暂时稳定，建议保留观察。"})
        for item in declining[:3]:
            items.append({**item, "risk_level": "low", "forecast": "风险呈恢复趋势，可降级观察。"})
        return items

    @staticmethod
    def _summary(status: str, rising: list[dict], declining: list[dict]) -> str:
        return f"风险预测状态为 {status}，上升风险 {len(rising)} 条，下降风险 {len(declining)} 条。本中心只读预测，不触发处理。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["优先人工查看 critical_forecasts。", "检查审批队列与执行计划是否存在治理风险。"]
        if status == "warning":
            return ["观察 rising_risks，并在周报中复盘。"]
        return ["保持常规风险趋势记录。"]

    @staticmethod
    def _format_item(item: dict) -> str:
        return f"- {item.get('title') or item.get('summary') or ''} / {item.get('trend') or ''} / {item.get('source') or ''}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("上升风险", "rising_risks"),
            ("稳定风险", "stable_risks"),
            ("下降风险", "declining_risks"),
            ("预测项", "forecast_items"),
            ("下周期观察", "next_period_watchlist"),
        ]
