"""Read-only entry router for AI Runtime OS dashboard."""


class AIRuntimeEntryRouterService:
    """Recommend the most relevant dashboard entry without executing actions."""

    @classmethod
    def build_entry_router(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        primary_entry = cls._primary_entry(dashboard)
        secondary_entries = cls._secondary_entries(dashboard, primary_entry)
        role_entries = cls._role_based_entries()
        risk_entries = cls._risk_based_entries(dashboard)
        quick_routes = cls._quick_routes()
        status = cls._router_status(primary_entry, risk_entries)

        return {
            "router_status": status,
            "summary": cls._summary(primary_entry, risk_entries),
            "primary_entry": primary_entry,
            "secondary_entries": secondary_entries,
            "role_based_entries": role_entries,
            "risk_based_entries": risk_entries,
            "quick_routes": quick_routes,
            "recommended_actions": cls._recommended_actions(primary_entry, risk_entries),
        }

    @classmethod
    def build_entry_router_text(cls, router: dict | None = None) -> str:
        router = router or {}
        primary = router.get("primary_entry") or {}
        lines = [
            "【AI Runtime OS 入口路由器】",
            f"状态：{router.get('router_status') or 'normal'}",
            f"摘要：{router.get('summary') or ''}",
            f"主入口：{primary.get('title') or ''} / {primary.get('route') or ''}",
            f"原因：{primary.get('reason') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            entries = router.get(key) or []
            if entries:
                for entry in entries:
                    lines.append(
                        f"- {entry.get('title')} / {entry.get('route')} / "
                        f"{entry.get('priority')} / {entry.get('reason')}"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_entry_router_markdown(cls, router: dict | None = None) -> str:
        router = router or {}
        primary = router.get("primary_entry") or {}
        lines = [
            "# AI Runtime OS 入口路由器",
            "",
            f"- 状态：{router.get('router_status') or 'normal'}",
            f"- 摘要：{router.get('summary') or ''}",
            f"- 主入口：[{primary.get('title') or ''}]({primary.get('route') or ''})",
            f"- 原因：{primary.get('reason') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            entries = router.get(key) or []
            if entries:
                for entry in entries:
                    lines.append(
                        f"- `{entry.get('title')}` {entry.get('priority')} / "
                        f"{entry.get('reason')} ({entry.get('route')})"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_entry_router_rows(cls, router: dict | None = None) -> list[dict]:
        router = router or {}
        rows = []
        primary = router.get("primary_entry") or {}
        if primary:
            rows.append(cls._row(primary, "primary"))
        for label, key in [
            ("secondary", "secondary_entries"),
            ("role", "role_based_entries"),
            ("risk", "risk_based_entries"),
            ("quick", "quick_routes"),
        ]:
            for entry in router.get(key) or []:
                rows.append(cls._row(entry, label))
        return rows

    @staticmethod
    def _row(entry: dict, entry_type: str) -> dict:
        return {
            "入口": entry.get("title") or "",
            "类型": entry_type,
            "Route": entry.get("route") or "",
            "优先级": entry.get("priority") or "",
            "原因": entry.get("reason") or "",
        }

    @classmethod
    def _primary_entry(cls, dashboard: dict) -> dict:
        practical = dashboard.get("ai_runtime_practical_console") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        mission = dashboard.get("ai_runtime_mission_control_center") or {}
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        kernel = dashboard.get("ai_runtime_os_kernel") or {}
        navigation = dashboard.get("ai_dashboard_navigation_center") or {}
        documentation = dashboard.get("ai_dashboard_documentation_center") or {}
        module_search = dashboard.get("ai_dashboard_module_search_center") or {}

        if practical.get("console_status") == "urgent":
            return cls._entry("AI Runtime 实用控制台", "/ai-dashboard", "Practical Console urgent，需要先看今日必须处理。", "urgent")
        if release.get("release_status") == "blocked":
            return cls._entry("AI Dashboard 上线准备度中心", "/ai-dashboard/release-readiness", "Release blocked，需要人工查看上线阻塞原因。", "urgent")
        if ops.get("ops_status") in {"critical", "risky"}:
            return cls._entry("AI Dashboard 运维健康中心", "/ai-dashboard/ops-health", "Ops critical，需要先查看运维健康。", "urgent")
        if mission.get("mission_status") == "critical":
            return cls._entry("AI Runtime 任务指挥中心", "/ai-dashboard/mission-control", "Mission critical，需要先查看任务指挥。", "urgent")

        if signal.get("signal_status") == "warning" or kernel.get("kernel_status") == "warning":
            return cls._entry("AI Runtime 任务指挥中心", "/ai-dashboard/mission-control", "Runtime warning，需要进入任务指挥观察。", "attention")
        if (
            navigation.get("navigation_status") in {"attention", "warning"}
            or documentation.get("documentation_status") in {"attention", "warning"}
        ):
            return cls._entry("AI Dashboard 导航中心", "/ai-dashboard/navigation", "存在文档或导航关注项。", "attention")
        if module_search.get("module_search_status") in {"attention", "warning"}:
            return cls._entry("AI Dashboard 模块搜索中心", "/ai-dashboard/module-search", "存在模块搜索关注项。", "attention")

        return cls._entry("AI Dashboard 管理首页中心", "/ai-dashboard/home", "当前无明显风险，进入管理首页总览。", "normal")

    @classmethod
    def _secondary_entries(cls, dashboard: dict, primary_entry: dict) -> list[dict]:
        candidates = [
            cls._entry("AI Runtime OS 分层首页", "/ai-dashboard", "按 7 层查看 Runtime OS。", "normal"),
            cls._entry("AI Runtime Practical Console", "/ai-dashboard#ai-runtime-practical-console", "查看五个运营视角。", "normal"),
            cls._entry("AI Runtime 任务指挥中心", "/ai-dashboard/mission-control", "查看今日任务和阻塞。", "normal"),
            cls._entry("AI Dashboard 模块搜索中心", "/ai-dashboard/module-search", "按模块名搜索入口。", "normal"),
        ]
        primary_route = primary_entry.get("route")
        return [entry for entry in candidates if entry.get("route") != primary_route][:4]

    @classmethod
    def _risk_based_entries(cls, dashboard: dict) -> list[dict]:
        entries = []
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}

        if release.get("release_status") == "blocked":
            entries.append(cls._entry("Release blocked", "/ai-dashboard/release-readiness", "上线准备度被阻塞。", "urgent"))
        if ops.get("ops_status") in {"warning", "critical", "risky"}:
            entries.append(cls._entry("Ops warning", "/ai-dashboard/ops-health", "运维健康存在关注项。", "attention"))
        if signal.get("signal_status") == "warning":
            entries.append(cls._entry("Runtime signal warning", "/ai-dashboard/mission-control", "Runtime 信号智能存在 warning。", "attention"))
        if judgment.get("judgment_status") == "critical" or court.get("court_status") == "critical":
            entries.append(cls._entry("Governance risk", "/ai-dashboard/mission-control", "治理判断或治理法庭存在 critical。", "urgent"))
        if export_ops.get("operations_status") in {"warning", "critical", "attention"}:
            entries.append(cls._entry("Export warning", "/ai-dashboard/export-operations", "导出运营存在关注项。", "attention"))
        return entries[:8]

    @staticmethod
    def _role_based_entries() -> list[dict]:
        return [
            {"title": "管理者", "route": "/ai-dashboard/home", "reason": "查看管理首页总览。", "priority": "normal"},
            {"title": "运维", "route": "/ai-dashboard/ops-health", "reason": "查看运维健康。", "priority": "normal"},
            {"title": "开发", "route": "/ai-dashboard/documentation", "reason": "查看文档与服务说明。", "priority": "normal"},
            {"title": "治理", "route": "/ai-dashboard/mission-control", "reason": "查看治理相关任务。", "priority": "normal"},
            {"title": "导出", "route": "/ai-dashboard/export-operations", "reason": "查看导出运营。", "priority": "normal"},
            {"title": "搜索", "route": "/ai-dashboard/module-search", "reason": "搜索 Dashboard 模块。", "priority": "normal"},
        ]

    @staticmethod
    def _quick_routes() -> list[dict]:
        return [
            {"title": "管理首页", "route": "/ai-dashboard/home", "reason": "管理首页总览。", "priority": "normal"},
            {"title": "分层首页", "route": "/ai-dashboard", "reason": "七层 Runtime 首页。", "priority": "normal"},
            {"title": "实用控制台", "route": "/ai-dashboard#ai-runtime-practical-console", "reason": "五个运营视角。", "priority": "normal"},
            {"title": "任务指挥", "route": "/ai-dashboard/mission-control", "reason": "今日任务和阻塞。", "priority": "normal"},
            {"title": "动作启动台", "route": "/ai-dashboard/action-launchpad", "reason": "只读动作入口清单。", "priority": "normal"},
            {"title": "模块搜索", "route": "/ai-dashboard/module-search", "reason": "搜索模块。", "priority": "normal"},
            {"title": "文档中心", "route": "/ai-dashboard/documentation", "reason": "查看文档。", "priority": "normal"},
            {"title": "导航中心", "route": "/ai-dashboard/navigation", "reason": "查看导航。", "priority": "normal"},
            {"title": "运维健康", "route": "/ai-dashboard/ops-health", "reason": "查看运维健康。", "priority": "normal"},
            {"title": "上线准备度", "route": "/ai-dashboard/release-readiness", "reason": "查看上线准备度。", "priority": "normal"},
            {"title": "导出运营", "route": "/ai-dashboard/export-operations", "reason": "查看导出运营。", "priority": "normal"},
            {"title": "冒烟测试", "route": "/ai-dashboard/smoke-test", "reason": "查看 Dashboard 冒烟测试。", "priority": "normal"},
        ]

    @staticmethod
    def _entry(title: str, route: str, reason: str, priority: str) -> dict:
        return {
            "title": title,
            "route": route,
            "reason": reason,
            "priority": priority,
        }

    @staticmethod
    def _router_status(primary_entry: dict, risk_entries: list[dict]) -> str:
        if primary_entry.get("priority") == "urgent" or any(entry.get("priority") == "urgent" for entry in risk_entries):
            return "urgent"
        if primary_entry.get("priority") == "attention" or risk_entries:
            return "attention"
        return "normal"

    @staticmethod
    def _summary(primary_entry: dict, risk_entries: list[dict]) -> str:
        if primary_entry.get("priority") == "urgent":
            return f"当前建议优先进入 {primary_entry.get('title')}，并保持人工只读复核。"
        if primary_entry.get("priority") == "attention":
            return f"当前建议进入 {primary_entry.get('title')} 观察关注项。"
        if risk_entries:
            return "当前存在风险入口建议，建议按风险入口逐项观察。"
        return "当前无明显入口风险，建议进入管理首页。"

    @staticmethod
    def _recommended_actions(primary_entry: dict, risk_entries: list[dict]) -> list[str]:
        actions = [
            f"优先进入：{primary_entry.get('title')} ({primary_entry.get('route')})。",
            "仅查看入口建议，不执行自动审核、发布或恢复动作。",
        ]
        if risk_entries:
            actions.append("按 risk_based_entries 查看风险对应入口。")
        return actions

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("辅助入口", "secondary_entries"),
            ("角色入口", "role_based_entries"),
            ("风险入口", "risk_based_entries"),
            ("快捷入口", "quick_routes"),
        ]
