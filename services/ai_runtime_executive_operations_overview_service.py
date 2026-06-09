"""Read-only Phase-3 executive operations overview aggregation."""


class AIRuntimeExecutiveOperationsOverviewService:
    """Aggregate executive, planning, and practical console signals."""

    @classmethod
    def build_executive_operations_overview(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        one_page = dashboard.get("ai_runtime_one_page_console") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        action_approval = dashboard.get("ai_runtime_action_approval_center") or {}
        execution_plan = dashboard.get("ai_runtime_execution_plan_center") or {}
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        monthly = dashboard.get("ai_runtime_monthly_board_report") or {}

        critical_items = cls._limit(
            cls._as_items(monthly.get("strategic_threats"), "Monthly Board")
            + cls._as_items(weekly.get("top_risks"), "Weekly Executive")
            + cls._as_items(action_approval.get("high_risk_pending"), "Action Approval")
            + cls._as_items(execution_plan.get("high_risk_plans"), "Execution Plan"),
            8,
        )
        today_focus = cls._limit(
            cls._as_items(one_page.get("today_must_do"), "One-Page Console")
            + cls._as_items(practical.get("must_handle_today") or practical.get("must_do_today"), "Practical Console"),
            6,
        )
        leadership_attention = cls._limit(
            critical_items
            + cls._as_items(monthly.get("quarter_focus"), "Monthly Board")
            + cls._as_items(weekly.get("next_week_priorities"), "Weekly Executive"),
            8,
        )
        status = cls._status(one_page, action_approval, execution_plan, weekly, monthly)
        return {
            "overview_status": status,
            "headline": cls._headline(status, critical_items),
            "executive_summary": cls._summary(status, critical_items, today_focus),
            "action_planning_summary": cls._action_planning_summary(action_approval, execution_plan),
            "practical_console_summary": cls._practical_console_summary(practical, one_page),
            "critical_items": critical_items,
            "today_focus": today_focus,
            "leadership_attention": leadership_attention,
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_executive_operations_overview_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "【AI Runtime 执行运营总览】",
            f"状态：{center.get('overview_status') or 'stable'}",
            f"摘要：{center.get('executive_summary') or ''}",
            "",
        ]
        for title, key in cls._sections():
            lines.append(f"{title}：")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_executive_operations_overview_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = [
            "# AI Runtime 执行运营总览",
            "",
            f"- 状态：{center.get('overview_status') or 'stable'}",
            f"- 摘要：{center.get('executive_summary') or ''}",
            "",
        ]
        for title, key in cls._sections():
            lines.append(f"## {title}")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_executive_operations_overview_rows(cls, center: dict | None = None) -> list[dict]:
        rows = []
        for section, key in cls._sections():
            for item in (center or {}).get(key) or []:
                rows.append({
                    "分类": section,
                    "项目": item.get("title") or item.get("summary") or "",
                    "状态": item.get("status") or item.get("priority") or item.get("risk_level") or "",
                    "风险": item.get("risk") or item.get("risk_level") or "",
                    "建议": item.get("suggestion") or item.get("summary") or "",
                })
        return rows

    @staticmethod
    def _status(one_page: dict, approval: dict, plan: dict, weekly: dict, monthly: dict) -> str:
        critical_values = {
            str(one_page.get("console_status") or "").lower(),
            str(approval.get("approval_status") or "").lower(),
            str(plan.get("plan_status") or "").lower(),
            str(weekly.get("report_status") or "").lower(),
            str(monthly.get("board_status") or "").lower(),
        }
        if critical_values & {"urgent", "blocked", "critical"}:
            return "critical"
        if critical_values & {"attention", "pending", "warning"}:
            return "attention"
        return "stable"

    @staticmethod
    def _headline(status: str, critical_items: list[dict]) -> str:
        if status == "critical":
            return "Runtime OS 存在高优先级治理或执行计划风险，需要高管关注。"
        if status == "attention":
            return "Runtime OS 整体可控，但审批、计划或运营侧存在观察项。"
        return "Runtime OS 运营总览稳定，当前以常规巡检和治理维护为主。"

    @staticmethod
    def _summary(status: str, critical_items: list[dict], today_focus: list[dict]) -> str:
        risk = critical_items[0].get("title") if critical_items else "暂无显著风险"
        focus = today_focus[0].get("title") if today_focus else "保持日常巡检"
        return f"当前状态为 {status}。最大关注点：{risk}。今日重点：{focus}。本模块仅聚合只读信息，不触发任何动作。"

    @staticmethod
    def _action_planning_summary(approval: dict, plan: dict) -> dict:
        return {
            "approval_status": approval.get("approval_status") or "empty",
            "pending_actions": len(approval.get("pending_actions") or []),
            "plan_status": plan.get("plan_status") or "empty",
            "planned_actions": len(plan.get("execution_plans") or []),
        }

    @staticmethod
    def _practical_console_summary(practical: dict, one_page: dict) -> dict:
        return {
            "console_status": one_page.get("console_status") or practical.get("console_status") or "normal",
            "must_do": len(one_page.get("today_must_do") or practical.get("must_handle_today") or []),
            "watch": len(one_page.get("today_watch") or practical.get("observe_today") or []),
            "never_do": len(one_page.get("never_do") or practical.get("never_automate") or []),
        }

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["先由负责人查看高风险审批与执行计划。", "保持只读分析，不从总览页触发动作。"]
        if status == "attention":
            return ["按今日重点检查任务优先级。", "关注审批队列和风险趋势变化。"]
        return ["维持日常巡检。", "按周报和月报节奏复盘。"]

    @staticmethod
    def _as_items(items, source: str) -> list[dict]:
        normalized = []
        for item in items or []:
            if isinstance(item, dict):
                normalized.append({**item, "source": item.get("source") or source})
            else:
                normalized.append({"title": str(item), "source": source})
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
            ("关键事项", "critical_items"),
            ("今日重点", "today_focus"),
            ("高管关注", "leadership_attention"),
        ]
