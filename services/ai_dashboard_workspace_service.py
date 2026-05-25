"""Read-only AI Dashboard role-based workspace center."""

from __future__ import annotations

from services.ai_dashboard_admin_home_service import AIDashboardAdminHomeService
from services.ai_dashboard_navigation_service import AIDashboardNavigationService


class AIDashboardWorkspaceService:
    """Build role-oriented Dashboard workspaces without triggering business actions."""

    @classmethod
    def build_workspace_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        admin_home = dashboard.get("ai_dashboard_admin_home_center") or AIDashboardAdminHomeService.build_admin_home_center(dashboard)
        navigation = dashboard.get("ai_dashboard_navigation_center") or dashboard.get("ai_dashboard_navigation_index_center") or AIDashboardNavigationService.build_navigation_center()

        manager_workspace = cls._workspace(
            "管理者工作台",
            "聚合高管视图、管理首页、周复盘、预测和持续改进。",
            ["Executive Dashboard", "Admin Home", "Weekly Review", "Forecast", "Continuous Improvement"],
            ["/ai-dashboard", "/ai-dashboard/admin-home"],
            ["/ai-dashboard/runtime-executive-dashboard-export?format=txt"],
            ["管理者路径", "导出/报表路径"],
            ["查看关键状态", "复核周复盘", "关注 Forecast 风险"],
            ["先看 Admin Home，再进入 Executive Dashboard"],
        )
        ops_workspace = cls._workspace(
            "运维工作台",
            "聚合运维健康、维护计划、导出运营、冒烟测试和 Runtime 告警事故。",
            ["Ops Health", "Ops Maintenance", "Export Operations", "Smoke Test", "Runtime Alert", "Runtime Incident"],
            ["/ai-dashboard/ops-health", "/ai-dashboard/ops-maintenance", "/ai-dashboard/export-operations", "/ai-dashboard/smoke-test"],
            ["/ai-dashboard/ops-health-export?format=txt", "/ai-dashboard/ops-maintenance-export?format=txt"],
            ["运维路径"],
            ["检查 Ops Health", "复核 Smoke Test", "查看导出调度"],
            ["优先处理 failed/critical 运维项"],
        )
        runtime_workspace = cls._workspace(
            "Runtime 工作台",
            "聚合快照、时间线、预测、预测动作、编排和持续改进。",
            ["Snapshot", "Timeline", "Forecast", "Predictive Action", "Orchestrator", "Continuous Improvement"],
            ["/ai-dashboard"],
            ["/ai-dashboard/runtime-snapshot-export?format=txt", "/ai-dashboard/runtime-forecast-export?format=txt"],
            ["Runtime 路径", "Runtime 治理路径"],
            ["查看 Snapshot", "复核 Timeline", "处理 Predictive Action"],
            ["只读分析 Runtime 趋势，不自动执行动作"],
        )
        developer_workspace = cls._workspace(
            "开发工作台",
            "聚合架构地图、文档、导航、Runtime Key、导出路由和模板标题检查。",
            ["Architecture Map", "Documentation", "Navigation", "Runtime Key Check", "Export Route Check", "Template Title Check"],
            ["/ai-dashboard/architecture-map", "/ai-dashboard/documentation", "/ai-dashboard/navigation-index", "/ai-dashboard/ops-health"],
            ["/ai-dashboard/architecture-map-export?format=txt", "/ai-dashboard/documentation-export?format=md"],
            ["开发者路径"],
            ["复核架构边界", "检查文档完整性", "查看路由和模板检查"],
            ["新增模块时同步文档、导航和测试"],
        )
        export_workspace = cls._workspace(
            "导出工作台",
            "聚合导出运营、导出自动化、调度导出、批量导出和索引导出。",
            ["Export Operations", "Export Automation", "Export Scheduler", "Batch Export", "Navigation Export", "Documentation Export"],
            ["/ai-dashboard/export-operations", "/ai-dashboard"],
            ["/ai-dashboard/export-all-reports?format=txt", "/ai-dashboard/navigation-index-export?format=csv", "/ai-dashboard/documentation-export?format=md"],
            ["导出/报表路径"],
            ["查看最新导出结果", "复核调度历史", "导出文档或导航索引"],
            ["导出前先检查 Export Operations 状态"],
        )
        documentation_workspace = cls._workspace(
            "文档工作台",
            "聚合文档中心、导航中心、架构地图、只读矩阵、Service 索引和 Route 索引。",
            ["Documentation", "Navigation", "Architecture Map", "Readonly Matrix", "Service Index", "Route Index"],
            ["/ai-dashboard/documentation", "/ai-dashboard/navigation-index", "/ai-dashboard/architecture-map"],
            ["/ai-dashboard/documentation-export?format=md", "/ai-dashboard/navigation-index-export?format=csv"],
            ["开发者路径"],
            ["检查模块目录", "复核只读矩阵", "更新索引视图"],
            ["保持文档与导航同步"],
        )
        governance_workspace = cls._workspace(
            "风险治理工作台",
            "聚合 Governance、Trust、Boundary、Constitution、Delegation Readiness、Policy Gate 和 Control Policy。",
            ["Governance", "Trust", "Boundary", "Constitution", "Delegation Readiness", "Policy Gate", "Control Policy"],
            ["/ai-dashboard"],
            ["/ai-dashboard/runtime-trust-export?format=txt", "/ai-dashboard/runtime-boundary-export?format=txt", "/ai-dashboard/runtime-constitution-export?format=txt"],
            ["Runtime 治理路径"],
            ["查看 Policy Gate", "复核 Trust 和 Boundary", "确认 Constitution 状态"],
            ["保持人工边界，不扩大自动化授权"],
        )

        workspaces = [
            manager_workspace,
            ops_workspace,
            runtime_workspace,
            developer_workspace,
            export_workspace,
            documentation_workspace,
            governance_workspace,
        ]
        recommended_workspace = cls._build_recommended_workspace(
            dashboard,
            admin_home,
            navigation,
            {
                "manager_workspace": manager_workspace,
                "ops_workspace": ops_workspace,
                "runtime_workspace": runtime_workspace,
                "developer_workspace": developer_workspace,
                "export_workspace": export_workspace,
                "documentation_workspace": documentation_workspace,
                "governance_workspace": governance_workspace,
            },
        )
        workspace_status = cls._resolve_workspace_status(workspaces, navigation)
        quick_actions = cls._build_quick_actions(workspaces)
        priority_work_items = cls._build_priority_work_items(workspaces, recommended_workspace)
        pending_items = cls._build_pending_items(admin_home, navigation)
        blocked_items = cls._build_blocked_items(dashboard, navigation)

        return {
            "workspace_status": workspace_status,
            "summary": cls._build_summary(workspace_status, workspaces, recommended_workspace),
            "today_workspace": {
                "title": recommended_workspace.get("title") or "管理者工作台",
                "status": workspace_status,
                "summary": recommended_workspace.get("reason") or recommended_workspace.get("summary") or "当前暂无 Dashboard 工作台数据。",
                "route": "/ai-dashboard/workspace",
            },
            "quick_actions": quick_actions,
            "priority_work_items": priority_work_items,
            "runtime_workbench": cls._workbench("runtime", runtime_workspace),
            "ops_workbench": cls._workbench("ops", ops_workspace),
            "export_workbench": cls._workbench("export", export_workspace),
            "governance_workbench": cls._workbench("governance", governance_workspace),
            "documentation_workbench": cls._workbench("documentation", documentation_workspace),
            "admin_workbench": cls._workbench("admin", manager_workspace),
            "pending_items": pending_items,
            "blocked_items": blocked_items,
            "manager_workspace": manager_workspace,
            "ops_workspace": ops_workspace,
            "runtime_workspace": runtime_workspace,
            "developer_workspace": developer_workspace,
            "export_workspace": export_workspace,
            "documentation_workspace": documentation_workspace,
            "governance_workspace": governance_workspace,
            "recommended_workspace": recommended_workspace,
            "recommended_actions": cls._build_recommended_actions(workspace_status),
        }

    @staticmethod
    def _workspace(
        title: str,
        summary: str,
        priority_modules: list[str],
        recommended_routes: list[str],
        recommended_exports: list[str],
        recommended_paths: list[str],
        daily_focus: list[str],
        recommended_actions: list[str],
    ) -> dict:
        return {
            "title": title,
            "summary": summary,
            "priority_modules": priority_modules,
            "recommended_routes": recommended_routes,
            "recommended_exports": recommended_exports,
            "recommended_paths": recommended_paths,
            "daily_focus": daily_focus,
            "recommended_actions": recommended_actions,
        }

    @classmethod
    def _build_recommended_workspace(cls, dashboard: dict, admin_home: dict, navigation: dict, workspaces: dict[str, dict]) -> dict:
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        documentation = dashboard.get("ai_dashboard_documentation_center") or {}
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        alert = dashboard.get("ai_runtime_alert_center") or {}

        if cls._status_in(ops.get("ops_status") or ops.get("health_status"), {"warning", "attention", "critical", "failed"}):
            result = dict(workspaces["ops_workspace"])
            result["reason"] = "Ops Health 存在 warning/critical 信号。"
            return result
        if cls._status_in(export_ops.get("operations_status") or export_ops.get("operation_status"), {"warning", "attention", "failed"}):
            result = dict(workspaces["export_workspace"])
            result["reason"] = "导出运营存在需要关注的状态。"
            return result
        if cls._status_in(forecast.get("forecast_status") or forecast.get("status"), {"warning", "attention", "risk", "critical"}):
            result = dict(workspaces["runtime_workspace"])
            result["reason"] = "Forecast 显示潜在 Runtime 风险。"
            return result
        if cls._status_in(documentation.get("documentation_status"), {"attention", "partial", "missing"}):
            result = dict(workspaces["documentation_workspace"])
            result["reason"] = "Documentation Center 信息不完整。"
            return result
        if cls._status_in(alert.get("alert_status"), {"warning", "critical"}):
            result = dict(workspaces["governance_workspace"])
            result["reason"] = "Runtime Alert 需要治理复核。"
            return result

        result = dict(workspaces["manager_workspace"])
        result["reason"] = (admin_home or {}).get("summary") or (navigation or {}).get("summary") or "当前优先使用管理者工作台总览全局。"
        return result

    @staticmethod
    def _workbench(workbench_type: str, workspace: dict) -> dict:
        workspace = workspace or {}
        return {
            "type": workbench_type,
            "title": workspace.get("title") or "",
            "status": "normal",
            "summary": workspace.get("summary") or "",
            "routes": workspace.get("recommended_routes") or [],
            "exports": workspace.get("recommended_exports") or [],
            "priority_modules": workspace.get("priority_modules") or [],
            "recommended_actions": workspace.get("recommended_actions") or [],
        }

    @staticmethod
    def _build_quick_actions(workspaces: list[dict]) -> list[dict]:
        actions = []
        for workspace in workspaces:
            routes = workspace.get("recommended_routes") or []
            actions.append({
                "type": "quick_action",
                "title": workspace.get("title") or "工作台",
                "status": "normal",
                "priority": "high" if len(actions) < 2 else "medium",
                "route": routes[0] if routes else "/ai-dashboard",
                "summary": workspace.get("summary") or "",
                "suggestion": "按角色进入对应工作台。",
            })
        return actions

    @staticmethod
    def _build_priority_work_items(workspaces: list[dict], recommended_workspace: dict) -> list[dict]:
        items = []
        recommended_title = (recommended_workspace or {}).get("title")
        for workspace in workspaces:
            modules = workspace.get("priority_modules") or []
            for index, module in enumerate(modules[:2]):
                items.append({
                    "type": "priority",
                    "title": module,
                    "status": "normal",
                    "priority": "high" if workspace.get("title") == recommended_title else ("medium" if index == 0 else "low"),
                    "route": (workspace.get("recommended_routes") or ["/ai-dashboard"])[0],
                    "summary": workspace.get("summary") or "",
                    "suggestion": "优先复核该工作项。",
                })
        return items[:10]

    @staticmethod
    def _build_pending_items(admin_home: dict, navigation: dict) -> list[dict]:
        items = []
        for item in (admin_home or {}).get("recommended_actions") or []:
            items.append({
                "type": "pending",
                "title": item,
                "status": "attention",
                "priority": "medium",
                "route": "/ai-dashboard/admin-home",
                "summary": "来自管理首页推荐动作。",
                "suggestion": item,
            })
        for path in (navigation or {}).get("recommended_paths") or []:
            items.append({
                "type": "pending",
                "title": path.get("name") or "推荐路径",
                "status": "normal",
                "priority": "low",
                "route": "/ai-dashboard/navigation-index",
                "summary": path.get("summary") or "",
                "suggestion": "按导航路径处理。",
            })
        return items[:8]

    @staticmethod
    def _build_blocked_items(dashboard: dict, navigation: dict) -> list[dict]:
        blocked = []
        for item in (navigation or {}).get("broken_routes") or []:
            blocked.append({
                "type": "blocked",
                "title": item.get("title") or item.get("path") or "异常路由",
                "status": "blocked",
                "priority": "high",
                "route": item.get("path") or "/ai-dashboard/navigation-index",
                "summary": item.get("summary") or "导航中心检测到异常路由。",
                "suggestion": item.get("suggestion") or "只读复核路由配置。",
            })
        for item in (dashboard or {}).get("ai_runtime_policy_gate_center", {}).get("forbidden_actions", []) or []:
            blocked.append({
                "type": "blocked",
                "title": item.get("title") if isinstance(item, dict) else str(item),
                "status": "blocked",
                "priority": "critical",
                "route": "/ai-dashboard",
                "summary": "策略闸门禁止的动作。",
                "suggestion": "保持人工复核，不自动执行。",
            })
        return blocked[:8]

    @staticmethod
    def _resolve_workspace_status(workspaces: list[dict], navigation: dict) -> str:
        module_count = sum(len(item.get("priority_modules") or []) for item in workspaces)
        runtime_count = len((workspaces[2] or {}).get("priority_modules") or [])
        ops_count = len((workspaces[1] or {}).get("priority_modules") or [])
        route_count = sum(len(item.get("recommended_routes") or []) for item in workspaces)
        path_count = len((navigation or {}).get("recommended_paths") or [])
        navigation_status = (navigation or {}).get("navigation_status") or ""

        if module_count > 44 or route_count > 28 or navigation_status in {"warning", "overloaded"}:
            return "attention"
        if runtime_count > 7 or ops_count > 5 or path_count > 7:
            return "warning"
        return "normal"

    @staticmethod
    def _status_in(status: str | None, values: set[str]) -> bool:
        return (status or "").strip().lower() in values

    @staticmethod
    def _build_summary(status: str, workspaces: list[dict], recommended_workspace: dict) -> str:
        if status == "attention":
            return f"AI Dashboard 工作台已聚合 {len(workspaces)} 个角色视图，但模块和入口较分散，建议优先进入 {recommended_workspace.get('title') or '推荐工作台'}。"
        if status == "warning":
            return f"AI Dashboard 工作台模块负载较高，建议按角色入口分流，当前推荐 {recommended_workspace.get('title') or '推荐工作台'}。"
        return f"AI Dashboard 工作台结构清晰，已聚合 {len(workspaces)} 个角色化工作台，当前推荐 {recommended_workspace.get('title') or '管理者工作台'}。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        actions = [
            "按角色进入对应工作台",
            "运维异常时优先进入运维工作台",
            "导出异常时优先进入导出工作台",
            "Forecast 风险出现时进入 Runtime 工作台",
            "文档缺失时进入文档工作台",
            "治理风险出现时进入风险治理工作台",
            "保持工作台只读聚合",
            "不要在工作台中加入审核发布动作",
        ]
        if status in {"attention", "warning"}:
            actions.insert(0, "优先使用推荐工作台降低入口复杂度")
        return actions[:8]

    @staticmethod
    def build_workspace_text(center: dict | None = None) -> str:
        center = center or AIDashboardWorkspaceService.build_workspace_center({})
        lines = [
            "【AI Dashboard 工作台中心】",
            "",
            f"工作台状态：{center.get('workspace_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "工作台列表：",
        ]
        for key in AIDashboardWorkspaceService._workspace_keys():
            workspace = center.get(key) or {}
            lines.append(f"- {workspace.get('title') or key}：{workspace.get('summary') or ''}")
        recommended = center.get("recommended_workspace") or {}
        lines.extend(["", f"推荐工作台：{recommended.get('title') or '-'}", f"推荐原因：{recommended.get('reason') or '-'}"])
        return "\n".join(lines)

    @staticmethod
    def build_workspace_markdown(center: dict | None = None) -> str:
        center = center or AIDashboardWorkspaceService.build_workspace_center({})
        lines = [
            "# AI Dashboard 工作台中心",
            "",
            f"- 工作台状态：{center.get('workspace_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 管理者工作台",
        ]
        for key, title in [
            ("manager_workspace", "管理者工作台"),
            ("ops_workspace", "运维工作台"),
            ("runtime_workspace", "Runtime 工作台"),
            ("developer_workspace", "开发工作台"),
            ("export_workspace", "导出工作台"),
            ("documentation_workspace", "文档工作台"),
            ("governance_workspace", "治理工作台"),
        ]:
            workspace = center.get(key) or {}
            if lines[-1] != f"## {title}":
                lines.extend(["", f"## {title}"])
            lines.append(workspace.get("summary") or "")
            lines.append(f"- 模块：{', '.join(workspace.get('priority_modules') or [])}")
            lines.append(f"- 路由：{', '.join(workspace.get('recommended_routes') or [])}")
        recommended = center.get("recommended_workspace") or {}
        lines.extend(["", "## 推荐工作台", f"- **{recommended.get('title') or '-'}**：{recommended.get('reason') or ''}"])
        return "\n".join(lines)

    @staticmethod
    def build_workspace_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardWorkspaceService.build_workspace_center({})
        rows = []
        for category, key in [
            ("快捷动作", "quick_actions"),
            ("优先事项", "priority_work_items"),
            ("待处理", "pending_items"),
            ("阻塞", "blocked_items"),
        ]:
            for item in center.get(key) or []:
                rows.append({
                    "分类": category,
                    "标题": item.get("title") or "",
                    "状态": item.get("status") or "",
                    "优先级": item.get("priority") or "",
                    "路径/入口": item.get("route") or "",
                    "摘要": item.get("summary") or "",
                    "建议": item.get("suggestion") or "",
                })
        for category, key in [
            ("运行时工作台", "runtime_workbench"),
            ("运维工作台", "ops_workbench"),
            ("导出工作台", "export_workbench"),
            ("治理工作台", "governance_workbench"),
            ("文档工作台", "documentation_workbench"),
            ("管理工作台", "admin_workbench"),
        ]:
            workbench = center.get(key) or {}
            rows.append({
                "分类": category,
                "标题": workbench.get("title") or "",
                "状态": workbench.get("status") or "",
                "优先级": "medium",
                "路径/入口": (workbench.get("routes") or [""])[0],
                "摘要": workbench.get("summary") or "",
                "建议": " / ".join(workbench.get("recommended_actions") or []),
            })
        return rows

    @staticmethod
    def _workspace_keys() -> list[str]:
        return [
            "manager_workspace",
            "ops_workspace",
            "runtime_workspace",
            "developer_workspace",
            "export_workspace",
            "documentation_workspace",
            "governance_workspace",
        ]
