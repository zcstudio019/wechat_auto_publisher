from __future__ import annotations


class AIDashboardActionLauncherService:
    """Read-only launcher aggregation for AI Dashboard navigation actions."""

    @classmethod
    def build_action_launchpad_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        launcher = cls.build_action_launcher_center(dashboard)
        all_actions = cls._normalize_launchpad_actions(launcher)
        quick_launch_actions = [item for item in all_actions if item.get("action_type") == "quick_launch"]
        safe_readonly_actions = [item for item in all_actions if item.get("safety_level") == "safe"]
        export_actions = [item for item in all_actions if item.get("action_type") == "export"]
        ops_actions = [item for item in all_actions if item.get("action_type") == "ops"]
        runtime_linked_actions = [item for item in all_actions if item.get("action_type") == "runtime"]
        approval_required_actions = [item for item in all_actions if item.get("requires_approval")]
        manual_confirm_actions = [item for item in all_actions if item.get("requires_manual_confirm")]
        risky_actions = [item for item in all_actions if item.get("safety_level") == "risky"]
        blocked_actions = [item for item in all_actions if item.get("safety_level") == "forbidden"]
        status = cls._launchpad_status(launcher.get("launcher_status"), risky_actions, blocked_actions)

        return {
            "launchpad_status": status,
            "summary": cls._build_launchpad_summary(status, all_actions),
            "action_groups": cls._build_action_groups(
                quick_launch_actions,
                safe_readonly_actions,
                runtime_linked_actions,
                export_actions,
                ops_actions,
                manual_confirm_actions,
                approval_required_actions,
                risky_actions,
                blocked_actions,
            ),
            "quick_launch_actions": quick_launch_actions,
            "manual_confirm_actions": manual_confirm_actions,
            "safe_readonly_actions": safe_readonly_actions,
            "risky_actions": risky_actions,
            "blocked_actions": blocked_actions,
            "approval_required_actions": approval_required_actions,
            "runtime_linked_actions": runtime_linked_actions,
            "export_actions": export_actions,
            "ops_actions": ops_actions,
            "recommended_actions": [
                "所有动作入口仅用于跳转或只读导出，不自动执行审核、发布或 worker。",
                "风险动作必须先进入复核、沙箱或审批流。",
                "优先使用安全只读动作查看状态，再决定是否进入人工流程。",
            ],
            "launcher_compat": launcher,
        }

    @classmethod
    def build_action_launcher_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        page_launchers = cls._page_launchers()
        workspace_launchers = cls._workspace_launchers()
        runtime_launchers = cls._runtime_launchers()
        ops_launchers = cls._ops_launchers()
        export_launchers = cls._export_launchers()
        documentation_launchers = cls._documentation_launchers()
        architecture_launchers = cls._architecture_launchers()
        search_launchers = cls._search_launchers()
        all_launchers = (
            page_launchers
            + workspace_launchers
            + runtime_launchers
            + ops_launchers
            + export_launchers
            + documentation_launchers
            + architecture_launchers
            + search_launchers
        )
        launcher_status = cls._resolve_status(dashboard, all_launchers)
        recommended_shortcuts = cls._recommended_shortcuts(dashboard)
        return {
            "launcher_status": launcher_status,
            "summary": cls._build_summary(launcher_status, all_launchers),
            "page_launchers": page_launchers,
            "workspace_launchers": workspace_launchers,
            "runtime_launchers": runtime_launchers,
            "ops_launchers": ops_launchers,
            "export_launchers": export_launchers,
            "documentation_launchers": documentation_launchers,
            "architecture_launchers": architecture_launchers,
            "search_launchers": search_launchers,
            "recommended_shortcuts": recommended_shortcuts,
            "recommended_actions": cls._recommended_actions(launcher_status),
        }

    @staticmethod
    def _launcher(title: str, route: str, summary: str, category: str, workspace: str = "") -> dict:
        return {
            "title": title,
            "route": route,
            "summary": summary,
            "category": category,
            "workspace": workspace,
        }

    @classmethod
    def _page_launchers(cls) -> list[dict]:
        return [
            cls._launcher("管理首页", "/ai-dashboard/home", "打开 AI Dashboard 管理首页。", "Page", "manager_workspace"),
            cls._launcher("工作台", "/ai-dashboard/workspace", "按角色进入工作台中心。", "Page", "manager_workspace"),
            cls._launcher("Mission Control", "/ai-dashboard/mission-control", "打开 Runtime 任务指挥中心。", "Page", "runtime_workspace"),
            cls._launcher("Navigation", "/ai-dashboard/navigation", "打开导航与索引中心。", "Page", "developer_workspace"),
            cls._launcher("Documentation", "/ai-dashboard/documentation", "打开文档中心。", "Page", "documentation_workspace"),
            cls._launcher("Module Search", "/ai-dashboard/module-search", "搜索模块、Route、Service 与 Dashboard key。", "Page", "developer_workspace"),
            cls._launcher("Architecture Map", "/ai-dashboard/architecture-map", "打开系统架构地图。", "Page", "developer_workspace"),
            cls._launcher("Ops Health", "/ai-dashboard/ops-health", "打开运维健康中心。", "Page", "ops_workspace"),
            cls._launcher("Export Operations", "/ai-dashboard/export-operations", "打开导出运营中心。", "Page", "export_workspace"),
            cls._launcher("Smoke Test", "/ai-dashboard/smoke-test", "打开冒烟测试中心。", "Page", "ops_workspace"),
        ]

    @classmethod
    def _workspace_launchers(cls) -> list[dict]:
        return [
            cls._launcher("manager_workspace", "/ai-dashboard/workspace?q=manager", "管理者工作台入口。", "Workspace", "manager_workspace"),
            cls._launcher("ops_workspace", "/ai-dashboard/workspace?q=ops", "运维工作台入口。", "Workspace", "ops_workspace"),
            cls._launcher("runtime_workspace", "/ai-dashboard/workspace?q=runtime", "Runtime 工作台入口。", "Workspace", "runtime_workspace"),
            cls._launcher("developer_workspace", "/ai-dashboard/workspace?q=developer", "开发与索引工作台入口。", "Workspace", "developer_workspace"),
            cls._launcher("governance_workspace", "/ai-dashboard/workspace?q=governance", "治理工作台入口。", "Workspace", "governance_workspace"),
            cls._launcher("export_workspace", "/ai-dashboard/workspace?q=export", "导出工作台入口。", "Workspace", "export_workspace"),
        ]

    @classmethod
    def _runtime_launchers(cls) -> list[dict]:
        return [
            cls._launcher("Snapshot", "/ai-dashboard#runtime-snapshot", "跳转 Runtime Snapshot。", "Runtime", "runtime_workspace"),
            cls._launcher("Timeline", "/ai-dashboard#runtime-timeline", "跳转 Runtime Timeline。", "Runtime", "runtime_workspace"),
            cls._launcher("Forecast", "/ai-dashboard#runtime-forecast", "跳转 Runtime Forecast。", "Runtime", "runtime_workspace"),
            cls._launcher("Predictive Action", "/ai-dashboard#runtime-predictive-action", "跳转预测动作中心。", "Runtime", "runtime_workspace"),
            cls._launcher("Continuous Improvement", "/ai-dashboard#runtime-continuous-improvement", "跳转持续改进中心。", "Runtime", "runtime_workspace"),
            cls._launcher("Orchestrator", "/ai-dashboard#runtime-orchestrator", "跳转 Runtime Orchestrator。", "Runtime", "runtime_workspace"),
            cls._launcher("Trust", "/ai-dashboard#runtime-trust", "跳转 Runtime Trust。", "Runtime", "governance_workspace"),
            cls._launcher("Constitution", "/ai-dashboard#runtime-constitution", "跳转 Runtime Constitution。", "Runtime", "governance_workspace"),
        ]

    @classmethod
    def _ops_launchers(cls) -> list[dict]:
        return [
            cls._launcher("Ops Health", "/ai-dashboard/ops-health", "查看 Dashboard 运维健康。", "Ops", "ops_workspace"),
            cls._launcher("Maintenance", "/ai-dashboard/ops-maintenance", "查看运维维护计划。", "Ops", "ops_workspace"),
            cls._launcher("Export Operations", "/ai-dashboard/export-operations", "查看导出运营详情。", "Ops", "export_workspace"),
            cls._launcher("Smoke Test", "/ai-dashboard/smoke-test", "运行前查看冒烟测试结果。", "Ops", "ops_workspace"),
            cls._launcher("Runtime Alert", "/ai-dashboard#runtime-alert", "跳转 Runtime Alert。", "Ops", "ops_workspace"),
            cls._launcher("Runtime Incident", "/ai-dashboard#runtime-incident", "跳转 Runtime Incident。", "Ops", "ops_workspace"),
        ]

    @classmethod
    def _export_launchers(cls) -> list[dict]:
        return [
            cls._launcher("批量导出", "/ai-dashboard/export-all-reports?format=zip", "批量导出 Dashboard 报表。", "Export", "export_workspace"),
            cls._launcher("调度导出", "/ai-dashboard/export-operations", "查看调度导出入口和历史。", "Export", "export_workspace"),
            cls._launcher("Weekly Review Export", "/ai-dashboard/runtime-weekly-review-export?format=txt", "导出 Runtime Weekly Review。", "Export", "runtime_workspace"),
            cls._launcher("Documentation Export", "/ai-dashboard/documentation-export?format=md", "导出文档中心 Markdown。", "Export", "documentation_workspace"),
            cls._launcher("Navigation Export", "/ai-dashboard/navigation-export?format=md", "导出导航中心 Markdown。", "Export", "documentation_workspace"),
            cls._launcher("Runtime Forecast Export", "/ai-dashboard/runtime-forecast-export?format=txt", "导出 Runtime Forecast。", "Export", "runtime_workspace"),
        ]

    @classmethod
    def _documentation_launchers(cls) -> list[dict]:
        return [
            cls._launcher("Documentation", "/ai-dashboard/documentation", "模块文档入口。", "Documentation", "documentation_workspace"),
            cls._launcher("Navigation", "/ai-dashboard/navigation", "导航索引入口。", "Documentation", "documentation_workspace"),
            cls._launcher("Route Index", "/ai-dashboard/module-search?q=route", "搜索 Route 索引。", "Documentation", "developer_workspace"),
            cls._launcher("Service Index", "/ai-dashboard/module-search?q=service", "搜索 Service 索引。", "Documentation", "developer_workspace"),
            cls._launcher("Readonly Matrix", "/ai-dashboard/documentation", "查看只读矩阵。", "Documentation", "documentation_workspace"),
        ]

    @classmethod
    def _architecture_launchers(cls) -> list[dict]:
        return [
            cls._launcher("Architecture Map", "/ai-dashboard/architecture-map", "系统架构地图入口。", "Architecture", "developer_workspace"),
            cls._launcher("Runtime Layers", "/ai-dashboard/architecture-map#runtime-layers", "查看 Runtime 层级。", "Architecture", "developer_workspace"),
            cls._launcher("Risk Propagation", "/ai-dashboard/architecture-map#risk-propagation", "查看风险传播路径。", "Architecture", "developer_workspace"),
            cls._launcher("Boundaries", "/ai-dashboard/architecture-map#boundaries", "查看自动化/人工/只读边界。", "Architecture", "governance_workspace"),
            cls._launcher("Constitution", "/ai-dashboard#runtime-constitution", "跳转 Constitution 模块。", "Architecture", "governance_workspace"),
        ]

    @classmethod
    def _search_launchers(cls) -> list[dict]:
        return [
            cls._launcher("搜索 Runtime", "/ai-dashboard/module-search?q=Runtime", "搜索 Runtime 模块。", "Search", "runtime_workspace"),
            cls._launcher("搜索 导出", "/ai-dashboard/module-search?q=导出", "搜索导出相关模块。", "Search", "export_workspace"),
            cls._launcher("搜索 文档", "/ai-dashboard/module-search?q=文档", "搜索文档相关模块。", "Search", "documentation_workspace"),
            cls._launcher("搜索 工作台", "/ai-dashboard/module-search?q=工作台", "搜索工作台相关入口。", "Search", "manager_workspace"),
            cls._launcher("搜索 Governance", "/ai-dashboard/module-search?q=Governance", "搜索治理相关模块。", "Search", "governance_workspace"),
        ]

    @staticmethod
    def _resolve_status(dashboard: dict, all_launchers: list[dict]) -> str:
        if len(all_launchers) > 60:
            return "overloaded"
        risk_values = [
            ((dashboard.get("ai_runtime_incident_center") or {}).get("incident_status") or "").lower(),
            ((dashboard.get("ai_dashboard_ops_health_center") or {}).get("ops_status") or "").lower(),
            ((dashboard.get("ai_runtime_forecast_center") or {}).get("forecast_status") or "").lower(),
            ((dashboard.get("ai_runtime_alert_center") or {}).get("alert_status") or "").lower(),
        ]
        if any(value in {"critical", "warning", "attention", "degraded", "high"} for value in risk_values):
            return "busy"
        return "ready"

    @staticmethod
    def _build_summary(status: str, all_launchers: list[dict]) -> str:
        if status == "overloaded":
            return f"AI Dashboard 动作启动台已聚合 {len(all_launchers)} 个入口，入口数量偏多，建议优先使用推荐快捷方式。"
        if status == "busy":
            return f"AI Dashboard 动作启动台已聚合 {len(all_launchers)} 个入口，当前 Runtime 或运维存在关注项。"
        return f"AI Dashboard 动作启动台已就绪，当前聚合 {len(all_launchers)} 个只读入口。"

    @classmethod
    def _recommended_shortcuts(cls, dashboard: dict) -> list[dict]:
        shortcuts = [
            cls._launcher("打开 Mission Control", "/ai-dashboard/mission-control", "先查看今日任务和阻塞项。", "Recommended", "runtime_workspace"),
            cls._launcher("打开工作台", "/ai-dashboard/workspace", "按角色选择入口。", "Recommended", "manager_workspace"),
        ]
        ops_status = ((dashboard.get("ai_dashboard_ops_health_center") or {}).get("ops_status") or "").lower()
        forecast_status = ((dashboard.get("ai_runtime_forecast_center") or {}).get("forecast_status") or "").lower()
        incident_status = ((dashboard.get("ai_runtime_incident_center") or {}).get("incident_status") or "").lower()
        if ops_status in {"warning", "critical", "attention"}:
            shortcuts.insert(0, cls._launcher("打开 Ops Health", "/ai-dashboard/ops-health", "优先检查运维健康风险。", "Recommended", "ops_workspace"))
        if forecast_status in {"warning", "critical", "high", "attention"}:
            shortcuts.append(cls._launcher("打开 Forecast", "/ai-dashboard#runtime-forecast", "查看预测风险和趋势。", "Recommended", "runtime_workspace"))
            shortcuts.append(cls._launcher("打开 Predictive Action", "/ai-dashboard#runtime-predictive-action", "查看预测动作建议。", "Recommended", "runtime_workspace"))
        if incident_status == "critical":
            shortcuts.insert(0, cls._launcher("打开 Runtime Incident", "/ai-dashboard#runtime-incident", "优先查看关键事件。", "Recommended", "ops_workspace"))
        shortcuts.append(cls._launcher("搜索模块", "/ai-dashboard/module-search", "按模块名、Route 或 Dashboard key 搜索。", "Recommended", "developer_workspace"))
        return shortcuts[:8]

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "overloaded":
            return ["优先使用推荐快捷方式", "后续按角色继续收敛入口", "保持启动台只读，不加入业务动作"]
        if status == "busy":
            return ["先打开 Mission Control", "再打开 Ops Health 或 Runtime Incident", "按工作台分流处理关注项"]
        return ["优先从管理首页或工作台进入", "使用模块搜索定位深层 Runtime 模块", "通过导出入口生成只读报告"]

    @classmethod
    def build_action_launcher_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_action_launcher_center()
        lines = [
            "【AI Dashboard 动作启动台中心】",
            f"状态：{center.get('launcher_status') or '-'}",
            center.get("summary") or "",
            "",
            "推荐快捷方式：",
        ]
        for item in center.get("recommended_shortcuts") or []:
            lines.append(f"- {item.get('title')} [{item.get('category')}] {item.get('route')}")
        return "\n".join(lines)

    @classmethod
    def build_action_launcher_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_action_launcher_center()
        lines = [
            "# AI Dashboard 动作启动台中心",
            "",
            f"- 状态：{center.get('launcher_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 页面动作入口",
        ]
        for item in center.get("page_launchers") or []:
            lines.append(f"- **{item.get('title')}**：`{item.get('route')}`")
        lines.append("")
        lines.append("## 工作台动作入口")
        for item in center.get("workspace_launchers") or []:
            lines.append(f"- **{item.get('title')}**：`{item.get('route')}`")
        lines.append("")
        lines.append("## Runtime 动作入口")
        for item in center.get("runtime_launchers") or []:
            lines.append(f"- **{item.get('title')}**：`{item.get('route')}`")
        lines.append("")
        lines.append("## 运维动作入口")
        for item in center.get("ops_launchers") or []:
            lines.append(f"- **{item.get('title')}**：`{item.get('route')}`")
        lines.append("")
        lines.append("## 导出动作入口")
        for item in center.get("export_launchers") or []:
            lines.append(f"- **{item.get('title')}**：`{item.get('route')}`")
        return "\n".join(lines)

    @classmethod
    def build_action_launcher_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_action_launcher_center()
        rows = []
        for key in [
            "page_launchers",
            "workspace_launchers",
            "runtime_launchers",
            "ops_launchers",
            "export_launchers",
            "documentation_launchers",
            "architecture_launchers",
            "search_launchers",
            "recommended_shortcuts",
        ]:
            for item in center.get(key) or []:
                rows.append({
                    "动作": item.get("title") or "",
                    "分类": item.get("category") or "",
                    "Route": item.get("route") or "",
                    "工作台": item.get("workspace") or "",
                    "说明": item.get("summary") or "",
                })
        return rows

    @classmethod
    def build_action_launchpad_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_action_launchpad_center()
        lines = [
            "【AI Dashboard 动作启动台中心】",
            f"状态：{center.get('launchpad_status') or '-'}",
            center.get("summary") or "",
            "",
            "快捷启动动作：",
        ]
        for item in center.get("quick_launch_actions") or []:
            lines.append(f"- {item.get('action_name')} [{item.get('safety_level')}] {item.get('route')}")
        return "\n".join(lines)

    @classmethod
    def build_action_launchpad_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_action_launchpad_center()
        rows = []
        for key in [
            "quick_launch_actions",
            "safe_readonly_actions",
            "runtime_linked_actions",
            "export_actions",
            "ops_actions",
            "manual_confirm_actions",
            "approval_required_actions",
            "risky_actions",
            "blocked_actions",
        ]:
            for item in center.get(key) or []:
                rows.append({
                    "动作分类": item.get("action_type_label") or "",
                    "动作名称": item.get("action_name") or "",
                    "状态": item.get("status") or "",
                    "安全级别": item.get("safety_level") or "",
                    "是否需要人工确认": "是" if item.get("requires_manual_confirm") else "否",
                    "是否需要审批": "是" if item.get("requires_approval") else "否",
                    "入口/路由": item.get("route") or "",
                    "建议": item.get("suggestion") or "",
                })
        if not rows:
            rows.append({
                "动作分类": "动作启动台",
                "动作名称": "当前暂无 Dashboard 动作启动台数据。",
                "状态": "idle",
                "安全级别": "safe",
                "是否需要人工确认": "否",
                "是否需要审批": "否",
                "入口/路由": "",
                "建议": "",
            })
        return rows

    @classmethod
    def _normalize_launchpad_actions(cls, launcher: dict) -> list[dict]:
        rows = []
        source_map = [
            ("quick_launch", "快捷启动", "recommended_shortcuts"),
            ("quick_launch", "快捷启动", "page_launchers"),
            ("runtime", "Runtime 关联", "runtime_launchers"),
            ("export", "导出动作", "export_launchers"),
            ("ops", "运维动作", "ops_launchers"),
            ("readonly", "安全只读", "workspace_launchers"),
            ("readonly", "安全只读", "documentation_launchers"),
            ("readonly", "安全只读", "architecture_launchers"),
            ("readonly", "安全只读", "search_launchers"),
        ]
        seen = set()
        for action_type, label, key in source_map:
            for item in launcher.get(key) or []:
                route = item.get("route") or ""
                identity = (item.get("title"), route)
                if identity in seen:
                    continue
                seen.add(identity)
                is_export = action_type == "export" or "export" in route.lower() or "导出" in (item.get("title") or "")
                safety_level = "safe"
                requires_manual = False
                requires_approval = False
                if route.startswith("/ai-dashboard/export-all-reports"):
                    safety_level = "review"
                    requires_manual = True
                if "publish" in route.lower() or "approve" in route.lower():
                    safety_level = "approval"
                    requires_approval = True
                rows.append({
                    "action_name": item.get("title") or "动作入口",
                    "action_type": "export" if is_export else action_type,
                    "action_type_label": "导出动作" if is_export else label,
                    "route": route,
                    "status": "normal",
                    "safety_level": safety_level,
                    "requires_manual_confirm": requires_manual,
                    "requires_approval": requires_approval,
                    "summary": item.get("summary") or "",
                    "suggestion": "只读打开入口，不自动执行动作。",
                })
        return rows

    @staticmethod
    def _launchpad_status(launcher_status: str | None, risky: list[dict], blocked: list[dict]) -> str:
        if blocked:
            return "blocked"
        if risky:
            return "warning"
        if launcher_status in {"busy", "overloaded"}:
            return "attention"
        return "normal"

    @staticmethod
    def _build_launchpad_summary(status: str, actions: list[dict]) -> str:
        if not actions:
            return "当前暂无 Dashboard 动作启动台数据。"
        if status in {"attention", "warning", "blocked"}:
            return f"动作启动台已聚合 {len(actions)} 个只读入口，部分动作需要人工复核或审批。"
        return f"动作启动台已就绪，当前聚合 {len(actions)} 个只读入口，不自动执行任何动作。"

    @staticmethod
    def _build_action_groups(*groups: list[dict]) -> list[dict]:
        labels = [
            "快捷启动动作",
            "安全只读动作",
            "Runtime 关联动作",
            "导出动作",
            "运维动作",
            "需人工确认动作",
            "需审批动作",
            "风险动作",
            "阻塞动作",
        ]
        return [
            {"title": label, "status": "normal" if items else "idle", "count": len(items)}
            for label, items in zip(labels, groups)
        ]
