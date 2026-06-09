"""Read-only Phase-3 task priority dynamic view."""


class AIRuntimeTaskPriorityViewService:
    """Build a priority view from existing Runtime centers."""

    @classmethod
    def build_task_priority_view(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        candidates = cls._collect_candidates(dashboard)
        p0, p1, p2, watch, blocked = [], [], [], [], []
        for item in candidates:
            priority = cls._priority(item)
            item["priority_bucket"] = priority
            if priority == "P0":
                p0.append(item)
            elif priority == "P1":
                p1.append(item)
            else:
                p2.append(item)
            if cls._is_watch(item):
                watch.append(item)
            if cls._is_blocked(item):
                blocked.append(item)

        status = "urgent" if p0 or blocked else "attention" if p1 or watch else "normal"
        return {
            "priority_status": status,
            "summary": cls._summary(status, p0, p1, watch),
            "p0_tasks": p0[:8],
            "p1_tasks": p1[:8],
            "p2_tasks": p2[:8],
            "watch_tasks": watch[:8],
            "blocked_tasks": blocked[:8],
            "priority_reasons": cls._priority_reasons(p0, p1, blocked),
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_task_priority_view_text(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["【AI Runtime 任务优先级动态视图】", f"状态：{center.get('priority_status') or 'normal'}", center.get("summary") or "", ""]
        for title, key in cls._sections():
            lines.append(f"{title}：")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_task_priority_view_markdown(cls, center: dict | None = None) -> str:
        center = center or {}
        lines = ["# AI Runtime 任务优先级动态视图", "", f"- 状态：{center.get('priority_status') or 'normal'}", f"- 摘要：{center.get('summary') or ''}", ""]
        for title, key in cls._sections():
            lines.append(f"## {title}")
            for item in (center.get(key) or [])[:12]:
                lines.append(cls._format_item(item))
            if not center.get(key):
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_task_priority_view_rows(cls, center: dict | None = None) -> list[dict]:
        rows = []
        for title, key in cls._sections():
            for item in (center or {}).get(key) or []:
                rows.append({
                    "任务": item.get("title") or item.get("summary") or "",
                    "优先级": item.get("priority_bucket") or item.get("priority") or "",
                    "来源": item.get("source") or "",
                    "状态": item.get("status") or item.get("risk_level") or "",
                    "建议入口": item.get("route") or item.get("recommended_route") or "/ai-dashboard",
                })
        return rows

    @classmethod
    def _collect_candidates(cls, dashboard: dict) -> list[dict]:
        sources = []
        daily = dashboard.get("ai_runtime_daily_operator_brief") or {}
        mission = dashboard.get("ai_runtime_mission_control_center") or dashboard.get("ai_runtime_task_command_center") or {}
        approval = dashboard.get("ai_runtime_action_approval_center") or {}
        plan = dashboard.get("ai_runtime_execution_plan_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}

        sources += cls._items(daily.get("must_do_today"), "Daily Brief")
        sources += cls._items(daily.get("watch_today"), "Daily Brief", default_priority="watch")
        sources += cls._items(daily.get("human_review_today"), "Daily Brief", default_priority="high")
        sources += cls._items(mission.get("critical_missions") or mission.get("active_missions"), "Mission Control")
        sources += cls._items(approval.get("pending_actions"), "Action Approval")
        sources += cls._items(approval.get("high_risk_pending"), "Action Approval", default_priority="critical")
        sources += cls._items(plan.get("execution_plans"), "Execution Plan")
        sources += cls._items(plan.get("high_risk_plans"), "Execution Plan", default_priority="high")
        sources += cls._items(ops.get("critical_risks") or ops.get("risks") or ops.get("warnings"), "Ops Health")
        sources += cls._items(release.get("must_fix_before_release") or release.get("release_risks"), "Release Readiness")
        return sources

    @staticmethod
    def _items(items, source: str, default_priority: str = "") -> list[dict]:
        normalized = []
        for item in items or []:
            if isinstance(item, dict):
                copied = dict(item)
            else:
                copied = {"title": str(item)}
            copied.setdefault("source", source)
            copied.setdefault("priority", default_priority)
            normalized.append(copied)
        return normalized

    @staticmethod
    def _priority(item: dict) -> str:
        text = " ".join(str(item.get(k) or "") for k in ("priority", "status", "risk_level", "title", "summary")).lower()
        if any(token in text for token in ("critical", "blocked", "urgent", "forbidden", "p0")):
            return "P0"
        if any(token in text for token in ("high", "warning", "attention", "conditional", "p1")):
            return "P1"
        return "P2"

    @staticmethod
    def _is_watch(item: dict) -> bool:
        text = " ".join(str(item.get(k) or "") for k in ("priority", "status", "title", "source")).lower()
        return "watch" in text or "observe" in text or "warning" in text

    @staticmethod
    def _is_blocked(item: dict) -> bool:
        text = " ".join(str(item.get(k) or "") for k in ("status", "risk_level", "title", "summary")).lower()
        return "blocked" in text or "forbidden" in text

    @staticmethod
    def _summary(status: str, p0: list[dict], p1: list[dict], watch: list[dict]) -> str:
        return f"当前任务优先级状态为 {status}，P0={len(p0)}，P1={len(p1)}，观察项={len(watch)}。"

    @staticmethod
    def _priority_reasons(p0: list[dict], p1: list[dict], blocked: list[dict]) -> list[str]:
        reasons = []
        if p0:
            reasons.append("存在 P0 级任务，需要优先人工查看。")
        if blocked:
            reasons.append("存在 blocked/forbidden 任务，只能进入人工复核。")
        if p1:
            reasons.append("存在 P1 级任务，建议纳入今日巡检。")
        return reasons or ["当前无明显优先级压力。"]

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "urgent":
            return ["先看 P0 和 blocked_tasks。", "不要从优先级视图触发任何动作。"]
        if status == "attention":
            return ["按 P1 和 watch_tasks 安排人工巡检。"]
        return ["保持常规任务节奏。"]

    @staticmethod
    def _format_item(item: dict) -> str:
        return f"- {item.get('title') or item.get('summary') or ''} / {item.get('priority_bucket') or ''} / {item.get('source') or ''}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("P0 任务", "p0_tasks"),
            ("P1 任务", "p1_tasks"),
            ("P2 任务", "p2_tasks"),
            ("观察任务", "watch_tasks"),
            ("阻塞任务", "blocked_tasks"),
        ]
