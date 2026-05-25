"""Read-only AI Dashboard admin home center."""

from __future__ import annotations

from services.ai_dashboard_documentation_service import AIDashboardDocumentationService
from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_navigation_service import AIDashboardNavigationService
from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService
from services.ai_dashboard_ops_maintenance_service import AIDashboardOpsMaintenanceService


class AIDashboardAdminHomeService:
    """Build a read-only admin home from existing AI Dashboard centers."""

    @classmethod
    def build_admin_home_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        ops_health = dashboard.get("ai_dashboard_ops_health_center") or AIDashboardOpsHealthService.build_ops_health_center()
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or AIDashboardExportOperationsService.build_export_operations_center()
        maintenance = (
            dashboard.get("ai_dashboard_ops_maintenance_center")
            or dashboard.get("ai_dashboard_ops_maintenance_plan_center")
            or AIDashboardOpsMaintenanceService.build_maintenance_plan()
        )
        documentation = dashboard.get("ai_dashboard_documentation_center") or AIDashboardDocumentationService.build_documentation_center()
        navigation = dashboard.get("ai_dashboard_navigation_center") or dashboard.get("ai_dashboard_navigation_index_center") or AIDashboardNavigationService.build_navigation_center()

        today_overview = cls._build_today_overview(dashboard, ops_health, export_ops, maintenance)
        critical_status_cards = cls._build_critical_status_cards(dashboard, ops_health, export_ops)
        quick_entries = cls._build_quick_entries(ops_health, export_ops, maintenance)
        runtime_entries = cls._build_runtime_entries()
        ops_entries = cls._build_ops_entries()
        doc_entries = cls._build_doc_entries()
        export_entries = cls._build_export_entries()
        architecture_entries = cls._build_architecture_entries()
        test_entries = cls._build_test_entries(ops_health)
        recommended_paths = cls._build_recommended_paths(navigation)
        home_status = cls._resolve_home_status(dashboard, ops_health, export_ops, maintenance)
        missing_entries = list((navigation or {}).get("missing_links") or [])

        return {
            "admin_home_status": home_status,
            "home_status": home_status,
            "summary": cls._build_summary(home_status, today_overview, quick_entries),
            "quick_entry_groups": [
                {"title": "快速入口", "entries": quick_entries},
                {"title": "Runtime 入口", "entries": runtime_entries},
                {"title": "运维入口", "entries": ops_entries},
                {"title": "文档入口", "entries": doc_entries},
                {"title": "导出入口", "entries": export_entries},
            ],
            "priority_modules": critical_status_cards,
            "runtime_overview": cls._overview_dict("Runtime 总览", runtime_entries, dashboard.get("ai_runtime_observability_center") or {}),
            "ops_overview": cls._overview_dict("运维总览", ops_entries, ops_health),
            "export_overview": cls._overview_dict("导出总览", export_entries, export_ops),
            "governance_overview": cls._overview_dict("治理总览", architecture_entries, dashboard.get("ai_governance_center") or {}),
            "documentation_overview": cls._overview_dict("文档总览", doc_entries, documentation),
            "navigation_overview": cls._overview_dict("导航总览", recommended_paths, navigation),
            "today_focus": today_overview,
            "system_shortcuts": quick_entries,
            "missing_entries": missing_entries,
            "today_overview": today_overview,
            "critical_status_cards": critical_status_cards,
            "quick_entries": quick_entries,
            "runtime_entries": runtime_entries,
            "ops_entries": ops_entries,
            "doc_entries": doc_entries,
            "export_entries": export_entries,
            "architecture_entries": architecture_entries,
            "test_entries": test_entries,
            "recommended_paths": recommended_paths,
            "recommended_actions": cls._build_recommended_actions(home_status, documentation),
        }

    @classmethod
    def _build_today_overview(cls, dashboard: dict, ops_health: dict, export_ops: dict, maintenance: dict) -> list[dict]:
        executive = dashboard.get("ai_runtime_executive_dashboard") or {}
        runtime_health = dashboard.get("ai_runtime_observability_center") or {}
        smoke = ops_health.get("smoke_test_status") or {}
        weekly = dashboard.get("ai_runtime_weekly_review_center") or {}
        return [
            cls._overview_item(
                "Executive Dashboard",
                executive.get("executive_status") or executive.get("status") or "unknown",
                executive.get("executive_summary") or executive.get("summary") or "当前暂无高管仪表盘摘要。",
            ),
            cls._overview_item(
                "Runtime Health",
                runtime_health.get("runtime_status") or runtime_health.get("status") or "unknown",
                ((runtime_health.get("runtime_health") or {}).get("summary")) or runtime_health.get("summary") or "当前暂无 Runtime 健康摘要。",
            ),
            cls._overview_item(
                "Ops Health",
                ops_health.get("ops_status") or ops_health.get("health_status") or "unknown",
                ops_health.get("summary") or "当前暂无运维健康摘要。",
            ),
            cls._overview_item(
                "Export Operations",
                export_ops.get("operations_status") or export_ops.get("operation_status") or "unknown",
                export_ops.get("summary") or "当前暂无导出运营摘要。",
            ),
            cls._overview_item(
                "Smoke Test",
                smoke.get("status") or "unknown",
                smoke.get("summary") or "当前暂无冒烟测试摘要。",
            ),
            cls._overview_item(
                "Weekly Review",
                weekly.get("review_status") or weekly.get("weekly_status") or weekly.get("status") or "unknown",
                weekly.get("weekly_summary") or weekly.get("summary") or "当前暂无周复盘摘要。",
            ),
            cls._overview_item(
                "Ops Maintenance",
                maintenance.get("maintenance_status") or "unknown",
                maintenance.get("summary") or "当前暂无维护计划摘要。",
            ),
        ]

    @classmethod
    def _build_critical_status_cards(cls, dashboard: dict, ops_health: dict, export_ops: dict) -> list[dict]:
        runtime = dashboard.get("ai_runtime_observability_center") or {}
        smoke = ops_health.get("smoke_test_status") or {}
        trust = dashboard.get("ai_runtime_trust_center") or {}
        boundary = dashboard.get("ai_runtime_boundary_center") or {}
        constitution = dashboard.get("ai_runtime_constitution_center") or {}
        return [
            cls._entry("Runtime Health", "/ai-dashboard", runtime.get("runtime_status") or "unknown", ((runtime.get("runtime_health") or {}).get("summary")) or "Runtime 健康状态。"),
            cls._entry("Ops Health", "/ai-dashboard/ops-health", ops_health.get("ops_status") or ops_health.get("health_status") or "unknown", ops_health.get("summary") or "Dashboard 运维健康状态。"),
            cls._entry("Export Status", "/ai-dashboard/export-operations", export_ops.get("operations_status") or export_ops.get("operation_status") or "unknown", export_ops.get("summary") or "导出运营状态。"),
            cls._entry("Smoke Test", "/ai-dashboard/smoke-test", smoke.get("status") or "unknown", smoke.get("summary") or "冒烟测试状态。"),
            cls._entry("Trust", "/ai-dashboard", trust.get("trust_status") or (trust.get("global_trust") or {}).get("level") or "unknown", trust.get("trust_summary") or "信任中心状态。"),
            cls._entry("Boundary", "/ai-dashboard", boundary.get("boundary_status") or "unknown", boundary.get("boundary_summary") or "边界中心状态。"),
            cls._entry("Constitution", "/ai-dashboard", constitution.get("constitution_status") or "unknown", constitution.get("constitution_summary") or "宪法中心状态。"),
        ]

    @staticmethod
    def _build_quick_entries(ops_health: dict, export_ops: dict, maintenance: dict) -> list[dict]:
        return [
            {"title": "高管仪表盘", "route": "/ai-dashboard", "summary": "查看 Runtime 高管汇总与关键风险。", "badge": "Executive"},
            {"title": "导航中心", "route": "/ai-dashboard/navigation-index", "summary": "查看 Dashboard 分类导航和索引。", "badge": "Navigation"},
            {"title": "文档中心", "route": "/ai-dashboard/documentation", "summary": "查看模块、路由、导出和测试文档。", "badge": "Docs"},
            {"title": "架构地图", "route": "/ai-dashboard/architecture-map", "summary": "查看系统架构层级与风险传播。", "badge": "Architecture"},
            {"title": "运维健康", "route": "/ai-dashboard/ops-health", "summary": ops_health.get("summary") or "查看 Dashboard 运维健康。", "badge": ops_health.get("ops_status") or ops_health.get("health_status") or "Ops"},
            {"title": "维护计划", "route": "/ai-dashboard/ops-maintenance", "summary": maintenance.get("summary") or "查看运维维护计划。", "badge": maintenance.get("maintenance_status") or "Maintenance"},
            {"title": "导出运营", "route": "/ai-dashboard/export-operations", "summary": export_ops.get("summary") or "查看导出运营状态。", "badge": export_ops.get("operations_status") or "Export"},
            {"title": "冒烟测试", "route": "/ai-dashboard/smoke-test", "summary": "查看 Dashboard 冒烟测试结果。", "badge": "Smoke"},
        ]

    @staticmethod
    def _build_runtime_entries() -> list[dict]:
        return [
            {"title": "Snapshot", "route": "/ai-dashboard", "summary": "查看 Runtime 快照。", "badge": "Runtime"},
            {"title": "Timeline", "route": "/ai-dashboard", "summary": "查看 Runtime 时间线。", "badge": "Runtime"},
            {"title": "Forecast", "route": "/ai-dashboard", "summary": "查看 Runtime 预测。", "badge": "Runtime"},
            {"title": "Predictive Action", "route": "/ai-dashboard", "summary": "查看预测动作建议。", "badge": "Runtime"},
            {"title": "Continuous Improvement", "route": "/ai-dashboard", "summary": "查看持续改进建议。", "badge": "Runtime"},
            {"title": "Orchestrator", "route": "/ai-dashboard", "summary": "查看 Runtime 编排中心。", "badge": "Governance"},
            {"title": "Control Policy", "route": "/ai-dashboard", "summary": "查看控制策略。", "badge": "Policy"},
            {"title": "Constitution", "route": "/ai-dashboard", "summary": "查看宪法与高约束原则。", "badge": "Boundary"},
        ]

    @staticmethod
    def _build_ops_entries() -> list[dict]:
        return [
            {"title": "Smoke Test", "route": "/ai-dashboard/smoke-test", "summary": "Dashboard 冒烟测试。", "badge": "Test"},
            {"title": "Ops Health", "route": "/ai-dashboard/ops-health", "summary": "Dashboard 运维健康中心。", "badge": "Ops"},
            {"title": "Ops Maintenance", "route": "/ai-dashboard/ops-maintenance", "summary": "运维维护计划。", "badge": "Plan"},
            {"title": "Export Operations", "route": "/ai-dashboard/export-operations", "summary": "导出运营中心。", "badge": "Export"},
            {"title": "Export Scheduler", "route": "/ai-dashboard", "summary": "调度日报导出入口。", "badge": "Schedule"},
            {"title": "Export Automation", "route": "/ai-dashboard/export-all-reports?format=txt", "summary": "批量导出报表入口。", "badge": "Automation"},
        ]

    @staticmethod
    def _build_doc_entries() -> list[dict]:
        return [
            {"title": "Documentation", "route": "/ai-dashboard/documentation", "summary": "统一文档中心。", "badge": "Docs"},
            {"title": "Navigation", "route": "/ai-dashboard/navigation-index", "summary": "导航与索引中心。", "badge": "Index"},
            {"title": "Architecture Map", "route": "/ai-dashboard/architecture-map", "summary": "系统架构地图。", "badge": "Map"},
        ]

    @staticmethod
    def _build_export_entries() -> list[dict]:
        return [
            {"title": "批量导出报表", "route": "/ai-dashboard/export-all-reports?format=txt", "summary": "导出全部 Dashboard 报表文本。", "badge": "TXT"},
            {"title": "调度日报导出", "route": "/ai-dashboard", "summary": "回到 Dashboard 使用调度日报导出入口。", "badge": "Schedule"},
            {"title": "Export Operations", "route": "/ai-dashboard/export-operations", "summary": "查看导出运营详情。", "badge": "Ops"},
            {"title": "Documentation Export", "route": "/ai-dashboard/documentation-export?format=md", "summary": "导出文档中心 Markdown。", "badge": "MD"},
            {"title": "Navigation Export", "route": "/ai-dashboard/navigation-index-export?format=csv", "summary": "导出导航中心表格。", "badge": "CSV"},
        ]

    @staticmethod
    def _build_architecture_entries() -> list[dict]:
        return [
            {"title": "Architecture Map", "route": "/ai-dashboard/architecture-map", "summary": "查看架构地图详情。", "badge": "Map"},
            {"title": "Runtime Layers", "route": "/ai-dashboard/architecture-map", "summary": "查看 Runtime 架构层级。", "badge": "Layer"},
            {"title": "Risk Propagation", "route": "/ai-dashboard/architecture-map", "summary": "查看风险传播路径。", "badge": "Risk"},
            {"title": "Boundaries", "route": "/ai-dashboard/architecture-map", "summary": "查看自动化、人工和只读边界。", "badge": "Boundary"},
        ]

    @staticmethod
    def _build_test_entries(ops_health: dict) -> list[dict]:
        route_status = ops_health.get("route_status") or {}
        template_status = ops_health.get("template_status") or {}
        runtime_status = ops_health.get("runtime_status") or {}
        return [
            {"title": "Smoke Test", "route": "/ai-dashboard/smoke-test", "summary": "运行 Dashboard 冒烟检查详情页。", "badge": (ops_health.get("smoke_test_status") or {}).get("status") or "Test"},
            {"title": "Ops Health", "route": "/ai-dashboard/ops-health", "summary": "查看运维健康诊断。", "badge": ops_health.get("ops_status") or "Ops"},
            {"title": "Runtime Key Check", "route": "/ai-dashboard/ops-health", "summary": runtime_status.get("summary") or "检查 Runtime key 完整性。", "badge": runtime_status.get("status") or "Check"},
            {"title": "Template Title Check", "route": "/ai-dashboard/ops-health", "summary": template_status.get("summary") or "检查模板标题完整性。", "badge": template_status.get("status") or "Check"},
            {"title": "Export Route Check", "route": "/ai-dashboard/ops-health", "summary": route_status.get("summary") or "检查导出路由完整性。", "badge": route_status.get("status") or "Check"},
        ]

    @staticmethod
    def _build_recommended_paths(navigation: dict) -> list[dict]:
        existing = list((navigation or {}).get("recommended_paths") or [])
        paths = [
            {"name": "管理者路径", "steps": ["高管仪表盘", "管理首页", "运维健康", "推荐动作"], "summary": "先看状态，再看风险和建议。"},
            {"name": "运维路径", "steps": ["运维健康", "维护计划", "导出运营", "冒烟测试"], "summary": "先定位健康风险，再复核维护和导出。"},
            {"name": "开发者路径", "steps": ["导航中心", "文档中心", "架构地图", "测试入口"], "summary": "先定位模块，再查看文档、架构和测试。"},
            {"name": "Runtime 治理路径", "steps": ["Orchestrator", "Control Policy", "Policy Gate", "Constitution"], "summary": "聚焦 Runtime 治理与边界。"},
            {"name": "导出/报表路径", "steps": ["Export Operations", "批量导出报表", "Documentation Export", "Navigation Export"], "summary": "聚焦报表导出与索引导出。"},
        ]
        return paths + existing[:3]

    @classmethod
    def _resolve_home_status(cls, dashboard: dict, ops_health: dict, export_ops: dict, maintenance: dict) -> str:
        executive = dashboard.get("ai_runtime_executive_dashboard") or {}
        incident = dashboard.get("ai_runtime_incident_center") or {}
        alert = dashboard.get("ai_runtime_alert_center") or {}
        smoke = ops_health.get("smoke_test_status") or {}

        critical_values = {"critical", "failed", "failure", "danger"}
        warning_values = {"warning", "attention", "degraded", "major", "urgent"}

        if (
            cls._status_in(executive.get("executive_status") or executive.get("status"), critical_values)
            or cls._status_in(ops_health.get("ops_status") or ops_health.get("health_status"), critical_values)
            or cls._status_in(smoke.get("status"), critical_values)
            or cls._status_in(incident.get("incident_status"), {"critical"})
        ):
            return "critical"

        if (
            cls._status_in(ops_health.get("ops_status") or ops_health.get("health_status"), warning_values)
            or cls._status_in(alert.get("alert_status"), {"warning", "critical"})
            or cls._status_in(export_ops.get("operations_status") or export_ops.get("operation_status"), warning_values)
            or cls._status_in(maintenance.get("maintenance_status"), warning_values)
        ):
            return "attention"
        return "normal"

    @staticmethod
    def _status_in(status: str | None, values: set[str]) -> bool:
        return (status or "").strip().lower() in values

    @staticmethod
    def _overview_item(title: str, status: str, summary: str) -> dict:
        return {"title": title, "status": status or "unknown", "summary": summary or ""}

    @staticmethod
    def _entry(title: str, route: str, status: str, summary: str) -> dict:
        return {"title": title, "route": route, "status": status or "unknown", "summary": summary or "", "badge": status or "status"}

    @staticmethod
    def _overview_dict(title: str, entries: list, source: dict) -> dict:
        source = source or {}
        status = (
            source.get("admin_home_status")
            or source.get("home_status")
            or source.get("health_status")
            or source.get("operation_status")
            or source.get("operations_status")
            or source.get("navigation_status")
            or source.get("documentation_status")
            or source.get("runtime_status")
            or source.get("governance_status")
            or "unknown"
        )
        if isinstance(status, dict):
            status = status.get("status") or status.get("level") or "unknown"
        return {
            "title": title,
            "status": status or "unknown",
            "summary": source.get("summary") or f"{title}当前共有 {len(entries or [])} 个入口。",
            "count": len(entries or []),
        }

    @staticmethod
    def _build_summary(status: str, today_overview: list[dict], quick_entries: list[dict]) -> str:
        if status == "critical":
            return "AI Dashboard 管理首页检测到关键风险，请优先查看运维健康、冒烟测试和 Runtime 事故状态。"
        if status == "attention":
            return "AI Dashboard 管理首页检测到需要关注的运维或 Runtime 信号，建议按推荐路径复核。"
        return f"AI Dashboard 管理首页已聚合 {len(today_overview)} 个今日总览项和 {len(quick_entries)} 个快速入口，当前无明显风险。"

    @staticmethod
    def _build_recommended_actions(status: str, documentation: dict) -> list[str]:
        actions = [
            "先查看关键状态卡，再进入对应中心",
            "运维异常时优先打开 Ops Health",
            "导出异常时优先打开 Export Operations",
            "新增模块时同步更新 Documentation 和 Navigation",
            "定期运行 Smoke Test",
            "通过 Architecture Map 复核模块边界",
            "保持管理首页只读聚合",
            "避免在首页引入审核发布动作",
        ]
        if status == "critical":
            actions.insert(0, "优先处理 critical 状态模块")
        if (documentation or {}).get("documentation_status") in {"attention", "partial", "missing"}:
            actions.insert(0, "补齐文档中心缺失信息")
        return actions[:8]

    @staticmethod
    def build_admin_home_text(center: dict | None = None) -> str:
        center = center or AIDashboardAdminHomeService.build_admin_home_center({})
        lines = [
            "【AI Dashboard 管理首页中心】",
            "",
            f"首页状态：{center.get('admin_home_status') or center.get('home_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "今日总览：",
        ]
        for item in center.get("today_overview") or []:
            lines.append(f"- {item.get('title')}：{item.get('status')} / {item.get('summary')}")
        lines.extend(["", "快速入口："])
        for item in center.get("quick_entries") or []:
            lines.append(f"- {item.get('title')}：{item.get('route')} / {item.get('summary')}")
        return "\n".join(lines)

    @staticmethod
    def build_admin_home_markdown(center: dict | None = None) -> str:
        center = center or AIDashboardAdminHomeService.build_admin_home_center({})
        lines = [
            "# AI Dashboard 管理首页中心",
            "",
            f"- 首页状态：{center.get('admin_home_status') or center.get('home_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 今日总览",
        ]
        for item in center.get("today_overview") or []:
            lines.append(f"- **{item.get('title')}**：{item.get('status')} / {item.get('summary')}")
        sections = [
            ("快速入口", "quick_entries"),
            ("Runtime 入口", "runtime_entries"),
            ("运维入口", "ops_entries"),
            ("文档入口", "doc_entries"),
            ("导出入口", "export_entries"),
            ("推荐路径", "recommended_paths"),
        ]
        for title, key in sections:
            lines.extend(["", f"## {title}"])
            for item in center.get(key) or []:
                if item.get("steps"):
                    lines.append(f"- **{item.get('name')}**：{' -> '.join(item.get('steps') or [])}")
                else:
                    lines.append(f"- **{item.get('title')}**：`{item.get('route') or ''}` / {item.get('summary') or ''}")
        return "\n".join(lines)

    @staticmethod
    def build_admin_home_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardAdminHomeService.build_admin_home_center({})
        rows = []
        section_map = [
            ("今日总览", "today_overview"),
            ("关键状态", "critical_status_cards"),
            ("快速入口", "quick_entries"),
            ("Runtime 入口", "runtime_entries"),
            ("运维入口", "ops_entries"),
            ("文档入口", "doc_entries"),
            ("导出入口", "export_entries"),
            ("架构入口", "architecture_entries"),
            ("测试入口", "test_entries"),
        ]
        for category, key in section_map:
            for item in center.get(key) or []:
                rows.append({
                    "分类": category,
                    "标题": item.get("title") or item.get("name") or "",
                    "路径/入口": item.get("route") or "",
                    "状态": item.get("status") or item.get("badge") or "",
                    "摘要": item.get("summary") or "",
                    "建议": item.get("suggestion") or "",
                })
        for item in center.get("recommended_paths") or []:
            rows.append({
                "分类": "推荐路径",
                "标题": item.get("name") or "",
                "路径/入口": "",
                "状态": "",
                "摘要": " -> ".join(item.get("steps") or []) or item.get("summary") or "",
                "建议": item.get("summary") or "",
            })
        return rows
