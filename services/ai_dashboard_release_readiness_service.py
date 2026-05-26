from __future__ import annotations

from services.ai_dashboard_architecture_map_service import AIDashboardArchitectureMapService
from services.ai_dashboard_documentation_service import AIDashboardDocumentationService
from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_navigation_service import AIDashboardNavigationService
from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService
from services.ai_dashboard_ops_maintenance_service import AIDashboardOpsMaintenanceService
from services.ai_dashboard_production_hardening_service import AIDashboardProductionHardeningService
from services.ai_dashboard_smoke_test_service import AIDashboardSmokeTestService


class AIDashboardReleaseReadinessService:
    """Read-only release readiness gate for AI Dashboard."""

    @classmethod
    def build_release_readiness_center(cls) -> dict:
        smoke = cls._safe_call(AIDashboardSmokeTestService.run_smoke_test)
        hardening = cls._safe_call(AIDashboardProductionHardeningService.build_production_hardening_center)
        ops = cls._safe_call(AIDashboardOpsHealthService.build_ops_health_center)
        maintenance = cls._safe_call(AIDashboardOpsMaintenanceService.build_maintenance_plan)
        documentation = cls._safe_call(AIDashboardDocumentationService.build_documentation_center)
        architecture = cls._safe_call(AIDashboardArchitectureMapService.build_architecture_map)
        navigation = cls._safe_call(AIDashboardNavigationService.build_navigation_center)
        export_ops = cls._safe_call(AIDashboardExportOperationsService.build_export_operations_center)

        blocking_checks = cls._build_blocking_checks(smoke, hardening, ops)
        warning_checks = cls._build_warning_checks(hardening, ops, maintenance, export_ops)
        passed_checks = cls._build_passed_checks(smoke, hardening, ops, documentation, navigation, export_ops, architecture)
        acceptable_risks = cls._build_acceptable_risks(warning_checks)
        must_fix = cls._build_must_fix_before_release(blocking_checks, hardening, ops)
        rollback = cls._build_rollback_readiness()
        ops_readiness = cls._build_ops_readiness(smoke, ops, maintenance, export_ops, documentation, navigation)
        deployment = cls._build_deployment_checklist()
        release_status = cls._resolve_status(blocking_checks, warning_checks)
        release_level = {"ready": "L1 可上线", "conditional": "L2 有条件上线", "blocked": "L3 暂缓上线"}[release_status]

        return {
            "release_status": release_status,
            "release_level": release_level,
            "summary": cls._build_summary(release_status, blocking_checks, warning_checks, passed_checks),
            "passed_checks": passed_checks,
            "warning_checks": warning_checks,
            "blocking_checks": blocking_checks,
            "acceptable_risks": acceptable_risks,
            "must_fix_before_release": must_fix,
            "rollback_readiness": rollback,
            "ops_readiness": ops_readiness,
            "deployment_checklist": deployment,
            "recommended_actions": cls._build_recommended_actions(release_status),
        }

    @staticmethod
    def _safe_call(fn) -> dict:
        try:
            value = fn()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"status": "failed", "summary": f"读取检查结果失败：{exc}"}

    @classmethod
    def _build_blocking_checks(cls, smoke: dict, hardening: dict, ops: dict) -> list[dict]:
        checks = []
        smoke_status = cls._status(smoke, "status", "smoke_status")
        failed_count = int(smoke.get("failed_count") or smoke.get("fail_count") or 0)
        if smoke_status in {"failed", "fail", "critical"} or failed_count > 0:
            checks.append(cls._check("Smoke Test fail", "blocked", "冒烟测试失败，上线前必须修复失败项。", "先修复 Smoke Test failed checks"))

        if cls._status(hardening, "hardening_status") == "risky":
            checks.append(cls._check("Production risky", "blocked", "Production Hardening 为 risky，暂缓上线。", "优先处理生产级加固高风险项"))

        if cls._status(ops, "ops_status", "health_status") in {"critical", "failed"}:
            checks.append(cls._check("Ops Health critical", "blocked", "Ops Health 处于 critical/failed 状态。", "先恢复运维健康中心"))

        for item in (hardening.get("permission_checks") or []):
            if item.get("status") == "risky":
                checks.append(cls._check("关键路由无权限保护", "blocked", item.get("summary") or "关键路由权限保护异常。", "复查关键路由 login_required 与权限守卫"))
                break
        for item in (hardening.get("route_security_checks") or []):
            text = f"{item.get('name', '')} {item.get('summary', '')}".lower()
            if item.get("status") == "risky" and any(key in text for key in ["route", "export", "download", "path", "post"]):
                checks.append(cls._check("导出路由缺失或高风险", "blocked", item.get("summary") or "导出/路由存在高风险。", "上线前复查导出和下载路由"))
                break
        return checks[:8]

    @classmethod
    def _build_warning_checks(cls, hardening: dict, ops: dict, maintenance: dict, export_ops: dict) -> list[dict]:
        checks = []
        if cls._status(hardening, "hardening_status") == "warning":
            checks.append(cls._check("Production Hardening warning", "warning", hardening.get("summary") or "生产加固存在关注项。", "部署前完成加固清单复核"))
        if cls._status(maintenance, "maintenance_status") in {"attention", "warning"}:
            checks.append(cls._check("Maintenance attention", "warning", maintenance.get("summary") or "维护计划存在关注项。", "复核运维维护计划"))
        notification = ops.get("export_operations_status", {}).get("notification_status") or ops.get("notification_status") or {}
        if notification and (not notification.get("email_enabled") or not notification.get("webhook_enabled")):
            checks.append(cls._check("通知未配置", "warning", "SMTP 或 Webhook 通知未完整配置。", "上线前配置邮件或 Webhook"))
        for item in (hardening.get("json_backup_checks") or []):
            if item.get("status") == "warning":
                checks.append(cls._check("JSON 文件需备份", "warning", item.get("summary") or "JSON 备份需补充。", "上线前备份 data JSON"))
                break
        for item in (hardening.get("large_file_risk_checks") or []):
            if item.get("status") in {"warning", "risky"}:
                checks.append(cls._check("导出文件或 JSON 较大", "warning", item.get("summary") or "文件体积需关注。", "检查导出目录大小"))
                break
        for item in (hardening.get("timeout_risk_checks") or []):
            if item.get("status") == "warning":
                checks.append(cls._check("页面较重", "warning", item.get("summary") or "Dashboard 页面可能偏重。", "上线前关注页面响应时间"))
                break
        if cls._status(export_ops, "operations_status") in {"warning", "failed"}:
            checks.append(cls._check("导出运营存在警告", "warning", export_ops.get("summary") or "导出运营存在关注项。", "复查 Export Operations"))
        if not checks:
            checks.append(cls._check("无明显 warning", "ok", "当前未识别到明确 warning。", "保持上线前复查"))
        return checks[:10]

    @classmethod
    def _build_passed_checks(cls, smoke: dict, hardening: dict, ops: dict, documentation: dict, navigation: dict, export_ops: dict, architecture: dict) -> list[dict]:
        checks = []
        if cls._status(smoke, "status", "smoke_status") in {"passed", "ok", "success", "healthy"} and not int(smoke.get("failed_count") or 0):
            checks.append(cls._check("Smoke Test 通过", "passed", smoke.get("summary") or "冒烟测试通过。", "上线前可保留记录"))
        if cls._status(ops, "ops_status", "health_status") in {"healthy", "normal", "ok"}:
            checks.append(cls._check("Ops Health 正常", "passed", ops.get("summary") or "运维健康正常。", "保持观察"))
        if cls._status(hardening, "hardening_status") in {"safe", "warning"}:
            checks.append(cls._check("Production Hardening safe/warning", "passed", hardening.get("summary") or "生产加固未阻断上线。", "按清单复查 warning"))
        if documentation:
            checks.append(cls._check("文档中心存在", "passed", documentation.get("summary") or "Documentation Center 可用。", "保持同步"))
        if navigation:
            checks.append(cls._check("导航中心存在", "passed", navigation.get("summary") or "Navigation Center 可用。", "保持同步"))
        if export_ops:
            checks.append(cls._check("导出中心存在", "passed", export_ops.get("summary") or "Export Operations 可用。", "保持只读导出"))
        if architecture:
            checks.append(cls._check("架构地图存在", "passed", architecture.get("summary") or "Architecture Map 可用。", "保持同步"))
        return checks

    @staticmethod
    def _build_acceptable_risks(warning_checks: list[dict]) -> list[dict]:
        risks = [
            {"risk": "页面模块较多但已折叠", "status": "acceptable", "summary": "主 Dashboard 已通过快捷入口和折叠降低首屏压力。"},
            {"risk": "部分导出文件较多", "status": "acceptable", "summary": "可在上线后按保留周期清理，前提是无 risky 大文件。"},
            {"risk": "部分通知未配置", "status": "acceptable", "summary": "可有条件上线，但需明确人工巡检窗口。"},
        ]
        if not warning_checks:
            risks.append({"risk": "无明显可接受风险", "status": "acceptable", "summary": "当前风险较低。"})
        return risks[:6]

    @classmethod
    def _build_must_fix_before_release(cls, blocking_checks: list[dict], hardening: dict, ops: dict) -> list[dict]:
        fixes = [dict(item) for item in blocking_checks]
        for item in (hardening.get("json_backup_checks") or []):
            if item.get("status") == "risky":
                fixes.append(cls._check("broken JSON", "blocked", item.get("summary") or "JSON 损坏或缺少备份。", "备份后人工修复 JSON"))
        for item in (hardening.get("route_security_checks") or []):
            if item.get("status") == "risky":
                fixes.append(cls._check("missing routes/security", "blocked", item.get("summary") or "路由安全风险。", "复查路由与权限"))
        if cls._status(ops, "ops_status", "health_status") == "critical":
            fixes.append(cls._check("critical ops risks", "blocked", "Ops Health critical。", "恢复运维健康后再上线"))
        return fixes[:10]

    @staticmethod
    def _build_rollback_readiness() -> list[dict]:
        return [
            {"item": "Git tag", "status": "manual", "summary": "上线前创建版本 tag，便于快速回退。"},
            {"item": "备份 data 目录", "status": "manual", "summary": "备份 data JSON、导出历史和快照文件。"},
            {"item": "备份 .env", "status": "manual", "summary": "保存当前环境变量配置，不输出敏感内容。"},
            {"item": "保留上一个可运行版本", "status": "manual", "summary": "保留上个 release 包或镜像。"},
            {"item": "systemd restart/rollback 命令说明", "status": "manual", "summary": "准备重启与回滚命令文档，不在本中心执行。"},
        ]

    @classmethod
    def _build_ops_readiness(cls, smoke: dict, ops: dict, maintenance: dict, export_ops: dict, documentation: dict, navigation: dict) -> list[dict]:
        return [
            cls._check("Smoke Test", cls._readiness_status(smoke, "status", "smoke_status"), smoke.get("summary") or "冒烟测试可用。", "上线前运行一次"),
            cls._check("Ops Health", cls._readiness_status(ops, "ops_status", "health_status"), ops.get("summary") or "运维健康中心可用。", "上线后持续观察"),
            cls._check("Maintenance Plan", cls._readiness_status(maintenance, "maintenance_status"), maintenance.get("summary") or "维护计划可用。", "上线前复核维护任务"),
            cls._check("Export Operations", cls._readiness_status(export_ops, "operations_status"), export_ops.get("summary") or "导出运营中心可用。", "确认导出不阻塞上线"),
            cls._check("Documentation", "passed" if documentation else "warning", documentation.get("summary") or "文档中心可用。", "保持文档同步"),
            cls._check("Navigation", "passed" if navigation else "warning", navigation.get("summary") or "导航中心可用。", "保持导航同步"),
        ]

    @staticmethod
    def _build_deployment_checklist() -> list[dict]:
        return [
            {"item": "py_compile", "status": "manual", "summary": "上线前执行 py_compile 检查关键文件。"},
            {"item": "unittest", "status": "manual", "summary": "上线前执行全量 unittest。"},
            {"item": "Nginx 检查", "status": "manual", "summary": "复查反向代理、超时和请求体限制。"},
            {"item": "systemd 检查", "status": "manual", "summary": "复查 restart policy 与日志路径。"},
            {"item": ".env 检查", "status": "manual", "summary": "复查密钥、权限和必填环境变量。"},
            {"item": "data 备份", "status": "manual", "summary": "备份 data 目录。"},
            {"item": "导出目录权限", "status": "manual", "summary": "确认导出目录不被静态任意访问。"},
            {"item": "日志轮转", "status": "manual", "summary": "配置应用和 Web 服务器日志轮转。"},
            {"item": "HTTPS", "status": "manual", "summary": "生产必须开启 HTTPS。"},
            {"item": "域名访问", "status": "manual", "summary": "确认域名、证书和健康检查。"},
        ]

    @staticmethod
    def _resolve_status(blocking: list[dict], warnings: list[dict]) -> str:
        if blocking:
            return "blocked"
        real_warnings = [item for item in warnings if item.get("status") == "warning"]
        if real_warnings:
            return "conditional"
        return "ready"

    @staticmethod
    def _build_summary(status: str, blocking: list[dict], warnings: list[dict], passed: list[dict]) -> str:
        if status == "blocked":
            return f"上线准备度阻断：存在 {len(blocking)} 个必须处理项，暂缓上线。"
        if status == "conditional":
            real_warnings = [item for item in warnings if item.get("status") == "warning"]
            return f"上线准备度为有条件上线：{len(passed)} 项通过，{len(real_warnings)} 项警告需人工接受。"
        return f"上线准备度通过：{len(passed)} 项核心检查已通过，可进入上线窗口。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        if status == "blocked":
            return ["先处理 blocking_checks", "修复 Smoke Test/Production/Ops 阻断项", "修复后重新运行上线准备度检查", "准备回滚包和 data 备份"]
        if status == "conditional":
            return ["人工确认 warning 是否可接受", "备份 data 和 .env", "执行 py_compile 与 unittest", "确认 Nginx/systemd/HTTPS", "上线后加强 Ops Health 观察"]
        return ["创建 Git tag", "备份 data 目录", "执行最终 unittest", "确认回滚说明", "进入上线窗口"]

    @staticmethod
    def _check(name: str, status: str, summary: str, suggestion: str) -> dict:
        return {"name": name, "status": status, "summary": summary, "suggestion": suggestion}

    @staticmethod
    def _status(source: dict, *keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if value:
                return str(value).strip().lower()
        return ""

    @classmethod
    def _readiness_status(cls, source: dict, *keys: str) -> str:
        status = cls._status(source, *keys)
        if status in {"passed", "ok", "success", "healthy", "normal", "safe", "ready"}:
            return "passed"
        if status in {"failed", "critical", "risky", "blocked"}:
            return "blocked"
        if status in {"warning", "attention", "conditional"}:
            return "warning"
        return "passed" if source else "warning"

    @classmethod
    def build_release_readiness_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_readiness_center()
        lines = [
            "【AI Dashboard 上线准备度中心】",
            f"状态：{center.get('release_status')} / {center.get('release_level')}",
            center.get("summary") or "",
            "",
            "阻断项：",
        ]
        for item in center.get("blocking_checks") or []:
            lines.append(f"- {item.get('name')}：{item.get('summary')}")
        lines.append("")
        lines.append("推荐动作：")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_release_readiness_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_readiness_center()
        lines = [
            "# AI Dashboard 上线准备度中心",
            "",
            f"- 状态：{center.get('release_status')}",
            f"- 等级：{center.get('release_level')}",
            f"- 摘要：{center.get('summary')}",
            "",
            "## 通过检查",
        ]
        for item in center.get("passed_checks") or []:
            lines.append(f"- **{item.get('name')}**：{item.get('summary')}")
        lines.append("")
        lines.append("## 警告检查")
        for item in center.get("warning_checks") or []:
            lines.append(f"- **{item.get('name')}** [{item.get('status')}]：{item.get('summary')}")
        lines.append("")
        lines.append("## 阻断检查")
        for item in center.get("blocking_checks") or []:
            lines.append(f"- **{item.get('name')}**：{item.get('summary')}")
        return "\n".join(lines)

    @classmethod
    def build_release_readiness_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_release_readiness_center()
        rows = []
        groups = [
            ("通过检查", "passed_checks"),
            ("警告检查", "warning_checks"),
            ("阻断检查", "blocking_checks"),
            ("可接受风险", "acceptable_risks"),
            ("上线前必须处理", "must_fix_before_release"),
            ("回滚准备", "rollback_readiness"),
            ("运维准备", "ops_readiness"),
            ("部署清单", "deployment_checklist"),
        ]
        for module, key in groups:
            for item in center.get(key) or []:
                rows.append({
                    "模块": module,
                    "检查项": item.get("name") or item.get("item") or item.get("risk") or "",
                    "状态": item.get("status") or "",
                    "摘要": item.get("summary") or "",
                    "建议": item.get("suggestion") or "",
                })
        return rows
