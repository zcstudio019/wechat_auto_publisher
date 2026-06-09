"""Read-only Phase-3 enhanced executive summary."""


class AIRuntimeEnhancedExecutiveSummaryService:
    """Combine weekly, monthly, approval, planning, and forecast summaries."""

    @classmethod
    def build_enhanced_executive_summary(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        monthly = dashboard.get("ai_runtime_monthly_board_report") or {}
        approval = dashboard.get("ai_runtime_action_approval_center") or {}
        plan = dashboard.get("ai_runtime_execution_plan_center") or {}
        forecast = dashboard.get("ai_runtime_risk_trend_forecast_center") or {}
        daily = dashboard.get("ai_runtime_daily_operator_brief") or {}

        status = cls._status(weekly, monthly, approval, plan, forecast)
        board_items = cls._limit(cls._items(monthly.get("strategic_threats"), "Monthly Board") + cls._items(forecast.get("critical_forecasts"), "Risk Forecast"), 8)
        cto_items = cls._limit(cls._items(plan.get("high_risk_plans"), "Execution Plan") + cls._items(weekly.get("top_risks"), "Weekly Executive"), 8)
        operator_items = cls._limit(cls._items(daily.get("must_do_today"), "Daily Brief") + cls._items(daily.get("watch_today"), "Daily Brief"), 8)
        return {
            "summary_status": status,
            "headline": cls._headline(status),
            "executive_brief": cls._brief(status, board_items, cto_items),
            "weekly_monthly_alignment": cls._weekly_monthly_alignment(weekly, monthly),
            "action_execution_alignment": cls._action_execution_alignment(approval, plan),
            "board_attention_items": board_items,
            "cto_attention_items": cto_items,
            "operator_attention_items": operator_items,
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_enhanced_executive_summary_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["【AI Runtime 高管摘要增强中心】", f"状态：{center.get('summary_status') or 'stable'}", center.get("executive_brief") or "", ""]
        for title, key in cls._sections():
            lines.append(f"{title}：")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_enhanced_executive_summary_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["# AI Runtime 高管摘要增强中心", "", f"- 状态：{center.get('summary_status') or 'stable'}", f"- 摘要：{center.get('executive_brief') or ''}", ""]
        for title, key in cls._sections():
            lines.append(f"## {title}")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_enhanced_executive_summary_rows(cls, center: dict | None = None) -> list[dict]:
        rows = []
        for title, key in cls._sections():
            for item in (center or {}).get(key) or []:
                rows.append({
                    "主题": title,
                    "状态": item.get("status") or item.get("summary_status") or "",
                    "风险": item.get("risk") or item.get("risk_level") or "",
                    "结论": item.get("title") or item.get("summary") or "",
                    "建议": item.get("suggestion") or "",
                })
        return rows

    @staticmethod
    def _status(weekly: dict, monthly: dict, approval: dict, plan: dict, forecast: dict) -> str:
        values = {
            str(weekly.get("report_status") or "").lower(),
            str(monthly.get("board_status") or "").lower(),
            str(approval.get("approval_status") or "").lower(),
            str(plan.get("plan_status") or "").lower(),
            str(forecast.get("forecast_status") or "").lower(),
        }
        if values & {"critical", "blocked", "urgent"}:
            return "critical"
        if values & {"attention", "warning", "pending"}:
            return "attention"
        return "stable"

    @staticmethod
    def _headline(status: str) -> str:
        if status == "critical":
            return "Runtime OS 高管摘要显示关键风险，需要董事会和技术负责人共同关注。"
        if status == "attention":
            return "Runtime OS 存在运营与治理观察项，建议纳入本周管理节奏。"
        return "Runtime OS 高管摘要稳定，周月报告与执行计划整体一致。"

    @staticmethod
    def _brief(status: str, board_items: list[dict], cto_items: list[dict]) -> str:
        board = board_items[0].get("title") if board_items else "暂无董事会级风险"
        cto = cto_items[0].get("title") if cto_items else "暂无 CTO 级风险"
        return f"当前摘要状态为 {status}。董事会关注：{board}。技术关注：{cto}。本中心只做高管摘要增强，不触发动作。"

    @staticmethod
    def _weekly_monthly_alignment(weekly: dict, monthly: dict) -> list[dict]:
        return [
            {
                "title": "Weekly / Monthly 状态对齐",
                "status": f"{weekly.get('report_status') or 'stable'} / {monthly.get('board_status') or 'healthy'}",
                "summary": "用于确认周报与月报风险口径是否一致。",
            }
        ]

    @staticmethod
    def _action_execution_alignment(approval: dict, plan: dict) -> list[dict]:
        return [
            {
                "title": "Approval / Execution Plan 对齐",
                "status": f"{approval.get('approval_status') or 'empty'} / {plan.get('plan_status') or 'empty'}",
                "summary": f"pending={len(approval.get('pending_actions') or [])}, planned={len(plan.get('execution_plans') or [])}",
            }
        ]

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["优先查看董事会关注与 CTO 关注项。", "保持所有处理在人工流程内。"]
        if status == "attention":
            return ["将观察项纳入本周管理例会。"]
        return ["继续按周报和月报节奏复盘。"]

    @staticmethod
    def _items(items, source: str) -> list[dict]:
        normalized = []
        for item in items or []:
            copied = dict(item) if isinstance(item, dict) else {"title": str(item)}
            copied.setdefault("source", source)
            normalized.append(copied)
        return normalized

    @staticmethod
    def _limit(items: list[dict], limit: int) -> list[dict]:
        return items[:limit]

    @staticmethod
    def _format_item(item: dict) -> str:
        return f"- {item.get('title') or item.get('summary') or ''} / {item.get('status') or item.get('risk_level') or ''} / {item.get('source') or ''}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("周月对齐", "weekly_monthly_alignment"),
            ("审批执行对齐", "action_execution_alignment"),
            ("董事会关注", "board_attention_items"),
            ("CTO 关注", "cto_attention_items"),
            ("运营关注", "operator_attention_items"),
        ]
