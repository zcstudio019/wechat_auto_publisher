from __future__ import annotations

from services.ai_dashboard_architecture_map_service import AIDashboardArchitectureMapService
from services.ai_dashboard_documentation_service import AIDashboardDocumentationService
from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_navigation_service import AIDashboardNavigationService
from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService
from services.ai_dashboard_production_hardening_service import AIDashboardProductionHardeningService
from services.ai_dashboard_release_readiness_service import AIDashboardReleaseReadinessService
from services.ai_dashboard_smoke_test_service import AIDashboardSmokeTestService
from services.ai_runtime_executive_digest_service import AIRuntimeExecutiveDigestService


class AIDashboardReleasePackageService:
    """Read-only release package checklist for AI Dashboard delivery."""

    @classmethod
    def build_release_package_center(cls) -> dict:
        readiness = cls._safe_call(AIDashboardReleaseReadinessService.build_release_readiness_center)
        smoke = cls._safe_call(AIDashboardSmokeTestService.run_smoke_test)
        hardening = cls._safe_call(AIDashboardProductionHardeningService.build_production_hardening_center)
        ops = cls._safe_call(AIDashboardOpsHealthService.build_ops_health_center)
        documentation = cls._safe_call(AIDashboardDocumentationService.build_documentation_center)
        architecture = cls._safe_call(AIDashboardArchitectureMapService.build_architecture_map)
        navigation = cls._safe_call(AIDashboardNavigationService.build_navigation_center)
        export_ops = cls._safe_call(AIDashboardExportOperationsService.build_export_operations_center)
        digest = cls._safe_call(AIRuntimeExecutiveDigestService.build_executive_digest)

        required_reports = cls._build_required_reports(
            readiness,
            hardening,
            ops,
            smoke,
            documentation,
            architecture,
            navigation,
            digest,
            export_ops,
        )
        package_status = cls._resolve_package_status(readiness, smoke, hardening, required_reports)
        release_readiness_snapshot = cls._snapshot(
            readiness,
            "release_status",
            warnings_key="warning_checks",
            blockers_key="blocking_checks",
        )
        production_hardening_snapshot = cls._snapshot(
            hardening,
            "hardening_status",
            warnings_key="production_risks",
            blockers_key="high_risk_gaps",
        )
        ops_health_snapshot = cls._snapshot(
            {**ops, "ops_status": ops.get("ops_status") or ops.get("health_status")},
            "ops_status",
            warnings_key="ops_risks",
            blockers_key="failed_items",
        )
        runtime_safety_snapshot = cls._runtime_safety_snapshot(hardening, ops, digest)
        package_checklist = cls._build_package_checklist(required_reports, readiness, hardening)
        blocking_issues = cls._build_blocking_issues(readiness, hardening, smoke)
        manual_confirmation_items = cls._build_manual_confirmation_items(readiness, hardening)

        return {
            "package_status": package_status,
            "package_version": cls._build_package_version(),
            "summary": cls._build_summary(package_status, required_reports),
            "release_readiness_snapshot": release_readiness_snapshot,
            "production_hardening_snapshot": production_hardening_snapshot,
            "ops_health_snapshot": ops_health_snapshot,
            "runtime_safety_snapshot": runtime_safety_snapshot,
            "included_modules": cls._build_included_modules(documentation, navigation, architecture),
            "included_routes": cls._build_included_routes(documentation),
            "included_templates": cls._build_included_templates(),
            "included_services": cls._build_included_services(),
            "included_exports": required_reports,
            "package_checklist": package_checklist,
            "blocking_issues": blocking_issues,
            "manual_confirmation_items": manual_confirmation_items,
            "release_summary": cls._build_release_summary(readiness),
            "required_reports": required_reports,
            "readiness_snapshot": release_readiness_snapshot,
            "smoke_test_snapshot": cls._snapshot(
                smoke,
                "status",
                warnings_key="warnings",
                blockers_key="failed_checks",
            ),
            "hardening_snapshot": production_hardening_snapshot,
            "documentation_snapshot": cls._documentation_snapshot(documentation),
            "architecture_snapshot": cls._architecture_snapshot(architecture),
            "rollback_package": cls._build_rollback_package(readiness, hardening),
            "ops_handoff_package": cls._build_ops_handoff_package(),
            "archive_suggestions": cls._build_archive_suggestions(export_ops),
            "package_file_checklist": cls._build_package_file_checklist(),
            "recommended_actions": cls._build_recommended_actions(package_status),
        }

    @staticmethod
    def _safe_call(fn) -> dict:
        try:
            value = fn()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"status": "failed", "summary": f"读取上线包依赖失败：{exc}"}

    @classmethod
    def _build_required_reports(
        cls,
        readiness: dict,
        hardening: dict,
        ops: dict,
        smoke: dict,
        documentation: dict,
        architecture: dict,
        navigation: dict,
        digest: dict,
        export_ops: dict,
    ) -> list[dict]:
        return [
            cls._report(
                "Release Readiness Report",
                cls._report_status(readiness, "release_status", ok={"ready"}, warn={"conditional"}),
                "/ai-dashboard/release-readiness-export?format=md",
                readiness.get("summary") or "上线准备度报告用于判断 ready/conditional/blocked。",
            ),
            cls._report(
                "Production Hardening Report",
                cls._report_status(hardening, "hardening_status", ok={"safe", "healthy"}, warn={"warning"}),
                "/ai-dashboard/production-hardening-export?format=txt",
                hardening.get("summary") or "生产级加固报告用于复核权限、路由、导出、备份和部署风险。",
            ),
            cls._report(
                "Ops Health Report",
                cls._report_status_any(ops, ["ops_status", "health_status"], ok={"healthy", "normal"}, warn={"warning", "attention"}),
                "/ai-dashboard/ops-health-export?format=md",
                ops.get("summary") or "运维健康报告用于确认 Dashboard 自身健康。",
            ),
            cls._report(
                "Smoke Test Report",
                cls._smoke_report_status(smoke),
                "/ai-dashboard/smoke-test",
                smoke.get("summary") or "冒烟测试报告用于确认关键 key、title、route 和 export 检查。",
            ),
            cls._report(
                "Documentation Report",
                cls._report_status(documentation, "documentation_status", ok={"complete"}, warn={"partial"}),
                "/ai-dashboard/documentation-export?format=md",
                documentation.get("summary") or "文档中心报告用于交付模块、路由、Service、测试和只读矩阵。",
            ),
            cls._report(
                "Architecture Map Report",
                cls._report_status(architecture, "architecture_status", ok={"stable"}, warn={"warning"}),
                "/ai-dashboard/architecture-map-export?format=md",
                architecture.get("summary") or "架构地图报告用于交付层级、依赖、边界和风险传播路径。",
            ),
            cls._report(
                "Navigation Report",
                cls._report_status(navigation, "navigation_status", ok={"clear"}, warn={"complex"}),
                "/ai-dashboard/navigation-export?format=md",
                navigation.get("summary") or "导航报告用于交付模块入口、路由入口和 Dashboard key 索引。",
            ),
            cls._report(
                "Executive Digest Report",
                cls._report_status(digest, "digest_status", ok={"stable"}, warn={"attention", "warning"}),
                "/ai-dashboard/executive-digest-export?format=md",
                digest.get("one_line_summary") or digest.get("summary") or "高层摘要报告用于 30 秒理解 Runtime 状态。",
            ),
            cls._report(
                "Export Operations Report",
                cls._report_status_any(export_ops, ["operations_status", "operation_status"], ok={"normal", "success"}, warn={"warning", "attention"}),
                "/ai-dashboard/export-operations",
                export_ops.get("summary") or "导出运营报告用于交付导出历史、文件、调度和通知状态。",
            ),
        ]

    @staticmethod
    def _report(name: str, status: str, export_route: str, summary: str) -> dict:
        return {"report": name, "status": status, "export_route": export_route, "summary": summary}

    @staticmethod
    def _report_status(source: dict, key: str, ok: set[str], warn: set[str]) -> str:
        value = str((source or {}).get(key) or "").strip().lower()
        if value in ok:
            return "ready"
        if value in warn:
            return "warning"
        if value in {"blocked", "failed", "fail", "critical", "risky"}:
            return "blocked"
        return "missing" if not source else "warning"

    @classmethod
    def _report_status_any(cls, source: dict, keys: list[str], ok: set[str], warn: set[str]) -> str:
        for key in keys:
            if (source or {}).get(key) is not None:
                return cls._report_status(source, key, ok, warn)
        return "missing" if not source else "warning"

    @staticmethod
    def _smoke_report_status(smoke: dict) -> str:
        status = str((smoke or {}).get("status") or (smoke or {}).get("smoke_status") or "").strip().lower()
        failed_count = int((smoke or {}).get("failed_count") or (smoke or {}).get("fail_count") or 0)
        if status in {"failed", "fail", "critical"} or failed_count > 0:
            return "blocked"
        if status in {"warning", "attention"}:
            return "warning"
        return "ready" if smoke else "missing"

    @classmethod
    def _resolve_package_status(cls, readiness: dict, smoke: dict, hardening: dict, reports: list[dict]) -> str:
        readiness_status = str(readiness.get("release_status") or readiness.get("readiness_status") or "").lower()
        hardening_status = str(hardening.get("hardening_status") or "").lower()
        if readiness_status == "blocked" or cls._smoke_report_status(smoke) == "blocked" or hardening_status in {"risky", "critical"}:
            return "blocked"
        if readiness_status == "conditional" or any(item.get("status") in {"warning", "missing"} for item in reports):
            return "draft"
        return "packaged"

    @staticmethod
    def _build_summary(status: str, reports: list[dict]) -> str:
        ready_count = sum(1 for item in reports if item.get("status") == "ready")
        warning_count = sum(1 for item in reports if item.get("status") == "warning")
        blocked_count = sum(1 for item in reports if item.get("status") == "blocked")
        if status == "blocked":
            return f"上线包暂不完整：存在 {blocked_count} 份阻断报告，需先处理上线阻断项。"
        if status in {"partial", "draft"}:
            return f"上线包可作为有条件交付材料：{ready_count} 份报告就绪，{warning_count} 份报告需人工复核。"
        return f"上线包核心材料齐全：{ready_count} 份关键报告已就绪，可进入归档和交接。"

    @staticmethod
    def _build_package_version() -> str:
        from datetime import datetime

        return f"ai-dashboard-{datetime.now().strftime('%Y%m%d')}"

    @classmethod
    def _runtime_safety_snapshot(cls, hardening: dict, ops: dict, digest: dict) -> dict:
        hardening_status = str(hardening.get("hardening_status") or "").lower()
        ops_status = str(ops.get("ops_status") or ops.get("health_status") or "").lower()
        digest_status = str(digest.get("digest_status") or "").lower()
        if hardening_status in {"risky", "critical"} or ops_status in {"critical", "failed"}:
            status = "critical"
        elif hardening_status in {"warning", "attention"} or ops_status in {"warning", "attention"} or digest_status in {"warning", "attention"}:
            status = "warning"
        elif hardening_status in {"safe", "healthy", "normal"} or ops_status in {"healthy", "normal"}:
            status = "healthy"
        else:
            status = "unknown"
        return {
            "status": status,
            "summary": digest.get("one_line_summary") or digest.get("summary") or "Runtime 安全快照由生产加固、运维健康和高层摘要聚合生成。",
            "warning_count": len(hardening.get("production_risks") or []),
            "blocking_count": len(hardening.get("high_risk_gaps") or []),
        }

    @staticmethod
    def _build_included_modules(documentation: dict, navigation: dict, architecture: dict) -> list[dict]:
        modules = [
            {"name": "AI Dashboard", "status": "included", "summary": "主 Dashboard 页面与总控区入口。"},
            {"name": "上线准备度中心", "status": "included", "summary": "上线前只读准备度检查。"},
            {"name": "生产级加固", "status": "included", "summary": "生产部署风险与加固清单。"},
            {"name": "运维健康中心", "status": "included", "summary": "Dashboard 运维健康状态。"},
        ]
        if documentation:
            modules.append({"name": "文档中心", "status": "included", "summary": documentation.get("summary") or "文档中心已纳入上线包。"})
        if navigation:
            modules.append({"name": "导航与索引中心", "status": "included", "summary": navigation.get("summary") or "导航入口已纳入上线包。"})
        if architecture:
            modules.append({"name": "系统架构地图中心", "status": "included", "summary": architecture.get("summary") or "架构地图已纳入上线包。"})
        return modules

    @staticmethod
    def _build_included_routes(documentation: dict) -> list[dict]:
        routes = [
            {"route": "/ai-dashboard", "status": "included", "summary": "AI Dashboard 主页面。"},
            {"route": "/ai-dashboard/release-package", "status": "included", "summary": "上线包详情页。"},
            {"route": "/ai-dashboard/release-package-export", "status": "included", "summary": "上线包只读导出接口。"},
            {"route": "/ai-dashboard/launch-readiness", "status": "included", "summary": "上线准备度详情页。"},
            {"route": "/ai-dashboard/production-hardening", "status": "included", "summary": "生产级加固详情页。"},
        ]
        for item in (documentation.get("route_docs") or [])[:8]:
            route = item.get("route") or item.get("path")
            if route:
                routes.append({"route": route, "status": item.get("status") or "included", "summary": item.get("summary") or ""})
        return routes

    @staticmethod
    def _build_included_templates() -> list[dict]:
        return [
            {"template": "ai_dashboard.html", "status": "included", "summary": "Dashboard 主模板。"},
            {"template": "ai_dashboard_release_package.html", "status": "included", "summary": "上线包详情模板。"},
            {"template": "ai_dashboard_launch_readiness.html", "status": "included", "summary": "上线准备度详情模板。"},
            {"template": "ai_dashboard_production_hardening.html", "status": "included", "summary": "生产级加固详情模板。"},
        ]

    @staticmethod
    def _build_included_services() -> list[dict]:
        return [
            {"service": "AIDashboardReleasePackageService", "status": "included", "summary": "上线包只读聚合服务。"},
            {"service": "AIDashboardLaunchReadinessService", "status": "included", "summary": "上线准备度只读聚合服务。"},
            {"service": "AIDashboardProductionHardeningService", "status": "included", "summary": "生产级加固只读聚合服务。"},
            {"service": "AIDashboardOpsHealthService", "status": "included", "summary": "运维健康只读聚合服务。"},
        ]

    @staticmethod
    def _build_package_checklist(required_reports: list[dict], readiness: dict, hardening: dict) -> list[dict]:
        checklist = [
            {"item": "上线准备度快照", "status": "pass" if readiness else "missing", "summary": "上线包必须包含上线准备度快照。"},
            {"item": "生产级加固快照", "status": "pass" if hardening else "missing", "summary": "上线包必须包含生产级加固快照。"},
            {"item": "导出报告清单", "status": "pass" if required_reports else "missing", "summary": "上线包必须列出导出报告。"},
            {"item": "回滚说明", "status": "manual_required", "summary": "上线前人工确认回滚说明。"},
            {"item": "data 备份", "status": "manual_required", "summary": "上线前人工确认 data 目录备份。"},
        ]
        return checklist

    @staticmethod
    def _build_blocking_issues(readiness: dict, hardening: dict, smoke: dict) -> list[dict]:
        issues = []
        for item in readiness.get("blocking_checks") or []:
            issues.append({"item": item.get("name") or "上线准备度阻塞", "status": "blocking", "summary": item.get("summary") or "", "suggestion": item.get("suggestion") or ""})
        for item in hardening.get("high_risk_gaps") or []:
            issues.append({"item": item.get("risk") or "生产级加固高风险", "status": "blocking", "summary": item.get("summary") or "", "suggestion": item.get("suggestion") or ""})
        for item in smoke.get("failed_checks") or []:
            issues.append({"item": item.get("name") or "冒烟测试失败", "status": "blocking", "summary": item.get("summary") or "", "suggestion": item.get("suggestion") or ""})
        return issues[:10]

    @staticmethod
    def _build_manual_confirmation_items(readiness: dict, hardening: dict) -> list[dict]:
        items = []
        for item in readiness.get("rollback_readiness") or []:
            items.append({"item": item.get("item") or item.get("name") or "回滚确认", "status": "manual_required", "summary": item.get("summary") or ""})
        for item in hardening.get("deployment_checklist") or []:
            if item.get("status") in {"manual", "manual_required", "warning"}:
                items.append({"item": item.get("item") or "部署确认", "status": "manual_required", "summary": item.get("summary") or ""})
        return items[:10]

    @staticmethod
    def _build_release_summary(readiness: dict) -> dict:
        actions = readiness.get("recommended_actions") or []
        return {
            "release_status": readiness.get("release_status") or "unknown",
            "release_level": readiness.get("release_level") or "unknown",
            "summary": readiness.get("summary") or "当前暂无上线准备度摘要。",
            "recommended_action": actions[0] if actions else "生成上线包后人工复核交付材料。",
        }

    @staticmethod
    def _snapshot(source: dict, status_key: str, warnings_key: str, blockers_key: str) -> dict:
        return {
            "status": (source or {}).get(status_key) or (source or {}).get("status") or "unknown",
            "summary": (source or {}).get("summary") or "暂无摘要。",
            "warnings": (source or {}).get(warnings_key) or [],
            "blockers": (source or {}).get(blockers_key) or [],
            "recommended_actions": ((source or {}).get("recommended_actions") or [])[:5],
        }

    @staticmethod
    def _documentation_snapshot(documentation: dict) -> dict:
        return {
            "status": documentation.get("documentation_status") or "unknown",
            "summary": documentation.get("summary") or "暂无文档中心摘要。",
            "module_count": len(documentation.get("module_catalog") or []),
            "route_count": len(documentation.get("route_docs") or []),
            "risk_summary": "文档、路由、导出与测试信息需保持同步。",
        }

    @staticmethod
    def _architecture_snapshot(architecture: dict) -> dict:
        risks = architecture.get("architecture_risks") or []
        return {
            "status": architecture.get("architecture_status") or "unknown",
            "summary": architecture.get("summary") or "暂无架构地图摘要。",
            "module_count": sum(len(item.get("modules") or []) for item in architecture.get("runtime_layers") or []),
            "route_count": len(architecture.get("data_dependencies") or []),
            "risk_summary": risks[0].get("summary") if risks and isinstance(risks[0], dict) else "架构边界与高耦合模块需持续观察。",
        }

    @staticmethod
    def _build_rollback_package(readiness: dict, hardening: dict) -> list[dict]:
        items = [
            {"item": "Git tag", "status": "manual", "summary": "上线前创建版本 tag，记录可回退提交。"},
            {"item": "data 目录备份", "status": "manual", "summary": "备份 data JSON、导出历史、快照和运维记录。"},
            {"item": ".env 备份", "status": "manual", "summary": "备份环境变量模板或密钥清单，不在报告中暴露敏感值。"},
            {"item": "上一个稳定版本", "status": "manual", "summary": "保留上一版代码包、镜像或部署产物。"},
            {"item": "systemd 回滚命令记录", "status": "manual", "summary": "记录 restart/rollback 命令说明，本中心不执行。"},
            {"item": "Nginx 配置备份", "status": "manual", "summary": "备份反向代理和证书配置说明，本中心不修改。"},
        ]
        for item in readiness.get("rollback_readiness") or []:
            title = item.get("item") or item.get("name")
            if title and not any(existing["item"] == title for existing in items):
                items.append({"item": title, "status": item.get("status") or "manual", "summary": item.get("summary") or ""})
        for item in hardening.get("deployment_checklist") or []:
            title = item.get("item") or item.get("name")
            if title and title in {"Nginx client_max_body_size", "systemd restart policy"}:
                items.append({"item": title, "status": "manual", "summary": item.get("summary") or "上线前人工确认。"})
        return items[:10]

    @staticmethod
    def _build_ops_handoff_package() -> list[dict]:
        return [
            {"item": "访问地址", "route": "/ai-dashboard", "summary": "上线后从 AI Dashboard 进入统一运营视图。"},
            {"item": "核心页面", "route": "/ai-dashboard/home", "summary": "管理首页用于日常入口聚合。"},
            {"item": "Smoke Test 路径", "route": "/ai-dashboard/smoke-test", "summary": "上线前后用于快速检查 Dashboard key/title/route/export。"},
            {"item": "Ops Health 路径", "route": "/ai-dashboard/ops-health", "summary": "用于运维健康巡检。"},
            {"item": "Export Operations 路径", "route": "/ai-dashboard/export-operations", "summary": "用于导出历史、调度和通知状态巡检。"},
            {"item": "Documentation 路径", "route": "/ai-dashboard/documentation", "summary": "用于模块、路由、Service 和测试交接。"},
            {"item": "Release Readiness 路径", "route": "/ai-dashboard/release-readiness", "summary": "用于上线准备度复核。"},
            {"item": "日常巡检建议", "route": "/ai-dashboard/production-hardening", "summary": "上线后定期复查生产加固、备份和日志轮转。"},
        ]

    @staticmethod
    def _build_archive_suggestions(export_ops: dict) -> list[dict]:
        return [
            {"item": "按日期归档上线报告", "status": "suggested", "summary": "建议使用 YYYY-MM-DD/release-package/ 归档上线材料。"},
            {"item": "导出 Markdown 总报告", "status": "suggested", "summary": "保留 Markdown 便于代码库和运维文档同步。"},
            {"item": "导出 ZIP 报表包", "status": "suggested", "summary": "如需 ZIP，使用现有导出中心能力，不在本中心自动打包。"},
            {"item": "备份 data JSON", "status": "suggested", "summary": "上线前后备份关键 JSON 文件。"},
            {"item": "记录测试结果", "status": "suggested", "summary": "归档 py_compile、专项 unittest、全量 unittest 输出。"},
            {"item": "导出运营记录", "status": "suggested", "summary": export_ops.get("summary") or "归档最近导出和调度导出状态。"},
        ]

    @staticmethod
    def _build_package_file_checklist() -> list[dict]:
        return [
            {"file": ".env.example", "status": "manual", "summary": "交付环境变量样例，不包含真实密钥。"},
            {"file": "requirements.txt", "status": "manual", "summary": "交付 Python 依赖清单。"},
            {"file": "README / 部署说明", "status": "manual", "summary": "交付安装、启动、检查和回滚说明。"},
            {"file": "data 备份说明", "status": "manual", "summary": "记录 data 目录备份范围和恢复方式。"},
            {"file": "SSL/Nginx 配置说明", "status": "manual", "summary": "交付 HTTPS、反向代理和上传/响应限制说明。"},
            {"file": "systemd 服务说明", "status": "manual", "summary": "交付服务名、restart policy、日志路径和回滚说明。"},
            {"file": "测试结果文本", "status": "manual", "summary": "归档 py_compile、专项测试和全量测试输出。"},
            {"file": "导出报告 ZIP", "status": "optional", "summary": "如需归档报表，使用现有导出接口生成后人工归档。"},
        ]

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        if status == "blocked":
            return [
                "先处理 Release Readiness 阻断项",
                "修复 Smoke Test 或 Production Hardening 高风险项",
                "重新生成上线包中心报告",
                "归档修复后的测试结果",
            ]
        if status == "draft":
            return [
                "人工确认 warning 报告是否可接受",
                "补齐缺失报告或导出材料",
                "备份 data 与 .env",
                "导出 TXT/CSV 上线包报告",
                "准备运维交接材料",
            ]
        return [
            "导出 TXT/CSV 上线包报告",
            "创建 Git tag",
            "备份 data 目录",
            "归档测试结果",
            "完成运维交接确认",
        ]

    @classmethod
    def build_release_package_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_package_center()
        lines = [
            "【AI Dashboard 上线包中心】",
            f"当前上线包状态：{center.get('package_status') or 'unknown'}",
            f"上线包版本：{center.get('package_version') or ''}",
            center.get("summary") or "",
            "",
            "快照：",
        ]
        for title, key in [
            ("上线准备度快照", "release_readiness_snapshot"),
            ("生产级加固快照", "production_hardening_snapshot"),
            ("运维健康快照", "ops_health_snapshot"),
            ("Runtime 安全快照", "runtime_safety_snapshot"),
        ]:
            item = center.get(key) or {}
            lines.append(f"- {title}：{item.get('status') or 'unknown'}；{item.get('summary') or ''}")
        lines.append("")
        lines.append("包含内容：")
        for title, key, name_key in [
            ("包含模块", "included_modules", "module"),
            ("包含路由", "included_routes", "route"),
            ("包含模板", "included_templates", "template"),
            ("包含服务", "included_services", "service"),
            ("包含导出接口", "included_exports", "export"),
        ]:
            lines.append(f"{title}：")
            for item in center.get(key) or []:
                lines.append(f"- {item.get(name_key) or item.get('title') or item.get('item') or ''} [{item.get('status') or ''}] {item.get('summary') or ''}")
        lines.append("")
        lines.append("上线检查：")
        for title, key in [
            ("上线包检查清单", "package_checklist"),
            ("阻塞问题", "blocking_issues"),
            ("需人工确认事项", "manual_confirmation_items"),
        ]:
            lines.append(f"{title}：")
            for item in center.get(key) or []:
                lines.append(f"- {item.get('title') or item.get('item') or ''} [{item.get('status') or ''}] {item.get('summary') or item.get('message') or ''}")
        lines.append("")
        lines.append("推荐动作：")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_release_package_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_package_center()
        lines = [
            "# AI Dashboard 上线包中心",
            "",
            f"- 状态：{center.get('package_status')}",
            f"- 摘要：{center.get('summary')}",
            "",
            "## 上线摘要",
        ]
        release = center.get("release_summary") or {}
        lines.extend([
            f"- 上线状态：{release.get('release_status')}",
            f"- 上线等级：{release.get('release_level')}",
            f"- 建议动作：{release.get('recommended_action')}",
            "",
            "## 必备报告",
        ])
        for item in center.get("required_reports") or []:
            lines.append(f"- **{item.get('report')}** [{item.get('status')}]：{item.get('export_route')}")
        lines.append("")
        lines.append("## 回滚准备材料")
        for item in center.get("rollback_package") or []:
            lines.append(f"- **{item.get('item')}**：{item.get('summary')}")
        lines.append("")
        lines.append("## 运维交接材料")
        for item in center.get("ops_handoff_package") or []:
            lines.append(f"- **{item.get('item')}**：{item.get('route')} - {item.get('summary')}")
        return "\n".join(lines)

    @classmethod
    def build_release_package_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_release_package_center()
        rows = []

        def add_row(category: str, item: dict, name_key: str = "title") -> None:
            rows.append({
                "分类": category,
                "项目": item.get(name_key) or item.get("title") or item.get("item") or item.get("module") or item.get("route") or item.get("template") or item.get("service") or item.get("export") or "",
                "状态": item.get("status") or "",
                "是否阻塞": "是" if item.get("blocking") is True or item.get("status") == "blocking" else "否",
                "是否需要人工确认": "是" if item.get("manual_required") is True or item.get("status") == "manual_required" else "否",
                "说明": item.get("summary") or item.get("message") or "",
                "建议动作": item.get("suggestion") or item.get("recommended_action") or "",
            })

        for title, key in [
            ("上线准备度快照", "release_readiness_snapshot"),
            ("生产级加固快照", "production_hardening_snapshot"),
            ("运维健康快照", "ops_health_snapshot"),
            ("Runtime 安全快照", "runtime_safety_snapshot"),
        ]:
            item = center.get(key) or {}
            rows.append({
                "分类": "核心快照",
                "项目": title,
                "状态": item.get("status") or "",
                "是否阻塞": "否",
                "是否需要人工确认": "否",
                "说明": item.get("summary") or "",
                "建议动作": item.get("recommended_action") or "",
            })
        for item in center.get("included_modules") or []:
            add_row("包含模块", item, "module")
        for item in center.get("included_routes") or []:
            add_row("包含路由", item, "route")
        for item in center.get("included_templates") or []:
            add_row("包含模板", item, "template")
        for item in center.get("included_services") or []:
            add_row("包含服务", item, "service")
        for item in center.get("included_exports") or []:
            add_row("包含导出接口", item, "export")
        for item in center.get("package_checklist") or []:
            add_row("上线包检查清单", item, "title")
        for item in center.get("blocking_issues") or []:
            add_row("阻塞问题", {**item, "blocking": True}, "title")
        for item in center.get("manual_confirmation_items") or []:
            add_row("需人工确认事项", {**item, "manual_required": True}, "title")
        for item in center.get("recommended_actions") or []:
            add_row("推荐处理动作", {"title": item, "status": "manual_required", "summary": item})
        return rows
