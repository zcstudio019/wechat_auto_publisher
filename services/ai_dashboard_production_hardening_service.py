from __future__ import annotations

import json
import re
from pathlib import Path


class AIDashboardProductionHardeningService:
    """Read-only production hardening checks for AI Dashboard."""

    ROOT = Path(__file__).resolve().parents[1]
    APP_FILE = ROOT / "web_ui" / "app.py"
    DATA_DIR = ROOT / "data"
    EXPORT_DIR = DATA_DIR / "ai_dashboard_exports"

    KEY_ROUTES = [
        "/ai-dashboard",
        "/ai-dashboard/export-all-reports",
        "/ai-dashboard/smoke-test",
        "/ai-dashboard/ops-health",
        "/ai-dashboard/documentation",
        "/ai-dashboard/navigation",
        "/ai-dashboard/action-launcher",
        "/ai-dashboard/executive-digest",
    ]

    KEY_JSON_FILES = [
        "ai_runtime_alerts.json",
        "ai_runtime_incidents.json",
        "ai_runtime_postmortems.json",
        "ai_runtime_learning.json",
        "ai_runtime_snapshots.json",
        "ai_dashboard_export_history.json",
        "ai_ops_score_history.json",
        "ai_ops_duty_history.json",
    ]

    @classmethod
    def build_production_hardening_center(cls) -> dict:
        app_text = cls._read_app_text()
        permission_checks = cls._build_permission_checks(app_text)
        route_security_checks = cls._build_route_security_checks(app_text)
        export_file_security_checks = cls._build_export_file_security_checks(app_text)
        json_backup_checks = cls._build_json_backup_checks()
        timeout_risk_checks = cls._build_timeout_risk_checks(app_text)
        large_file_risk_checks = cls._build_large_file_risk_checks()
        fallback_checks = cls._build_fallback_checks(app_text)
        audit_log_suggestions = cls._build_audit_log_suggestions()
        deployment_checklist = cls._build_deployment_checklist()
        production_risks = cls._build_production_risks(
            route_security_checks,
            export_file_security_checks,
            json_backup_checks,
            timeout_risk_checks,
            large_file_risk_checks,
        )
        hardening_status = cls._resolve_status(
            permission_checks,
            route_security_checks,
            export_file_security_checks,
            json_backup_checks,
            large_file_risk_checks,
            production_risks,
        )
        normalized_status = cls._normalize_dashboard_status(hardening_status)
        security_checklist = fallback_checks + audit_log_suggestions
        runtime_safety_checklist = timeout_risk_checks + large_file_risk_checks
        export_safety_checklist = export_file_security_checks
        ops_safety_checklist = fallback_checks
        permission_checklist = permission_checks
        route_hardening_checklist = route_security_checks
        json_file_hardening_checklist = json_backup_checks
        template_hardening_checklist = cls._build_template_hardening_checklist()
        high_risk_gaps = production_risks

        return {
            "hardening_status": normalized_status,
            "summary": cls._build_summary(hardening_status, production_risks),
            "security_checklist": security_checklist,
            "runtime_safety_checklist": runtime_safety_checklist,
            "export_safety_checklist": export_safety_checklist,
            "ops_safety_checklist": ops_safety_checklist,
            "permission_checklist": permission_checklist,
            "route_hardening_checklist": route_hardening_checklist,
            "json_file_hardening_checklist": json_file_hardening_checklist,
            "template_hardening_checklist": template_hardening_checklist,
            "high_risk_gaps": high_risk_gaps,
            "permission_checks": permission_checks,
            "route_security_checks": route_security_checks,
            "export_file_security_checks": export_file_security_checks,
            "json_backup_checks": json_backup_checks,
            "timeout_risk_checks": timeout_risk_checks,
            "large_file_risk_checks": large_file_risk_checks,
            "fallback_checks": fallback_checks,
            "audit_log_suggestions": audit_log_suggestions,
            "deployment_checklist": deployment_checklist,
            "production_risks": production_risks,
            "recommended_actions": cls._build_recommended_actions(hardening_status),
        }

    @staticmethod
    def _normalize_dashboard_status(status: str) -> str:
        if status == "risky":
            return "critical"
        if status == "safe":
            return "healthy"
        return status or "unknown"

    @staticmethod
    def _build_template_hardening_checklist() -> list[dict]:
        return [
            {
                "name": "Jinja safe access",
                "status": "manual_required",
                "summary": "生产环境需持续使用 dashboard.get 与 list fallback，避免 UndefinedError。",
            },
            {
                "name": "Empty state fallback",
                "status": "manual_required",
                "summary": "关键 Dashboard 卡片必须在空数据时仍显示中文兜底。",
            },
            {
                "name": "UTF-8 rendering",
                "status": "manual_required",
                "summary": "模板中文标题需保持 UTF-8，确保 Ctrl+F 可搜索。",
            },
        ]

    @classmethod
    def _read_app_text(cls) -> str:
        try:
            return cls.APP_FILE.read_text(encoding="utf-8")
        except Exception:
            return ""

    @classmethod
    def _build_permission_checks(cls, app_text: str) -> list[dict]:
        checks = []
        for route in cls.KEY_ROUTES:
            block = cls._route_block(app_text, route)
            exists = bool(block)
            protected = "@login_required" in block
            guarded = "_can_view_ai_dashboard_exports" in block or "get_perms()" in block or route == "/ai-dashboard"
            if exists and protected and guarded:
                status = "ok"
                summary = "路由存在登录与 Dashboard 权限保护。"
            elif exists and protected:
                status = "warning"
                summary = "路由存在登录保护，建议复查 Dashboard 细粒度权限。"
            elif exists:
                status = "risky"
                summary = "路由存在但未识别到登录保护。"
            else:
                status = "warning"
                summary = "未在 app.py 中识别到该关键路由，建议部署前复查。"
            checks.append({"route": route, "status": status, "summary": summary})
        return checks

    @staticmethod
    def _route_block(app_text: str, route: str) -> str:
        marker = f'@app.route("{route}")'
        index = app_text.find(marker)
        if index < 0:
            return ""
        next_route = app_text.find("\n@app.route", index + len(marker))
        if next_route < 0:
            next_route = app_text.find("\ndef ", index + len(marker) + 1)
        if next_route < 0:
            next_route = min(len(app_text), index + 1200)
        return app_text[index:next_route]

    @staticmethod
    def _build_route_security_checks(app_text: str) -> list[dict]:
        ai_dashboard_routes = re.findall(r'@app\.route\("(/ai-dashboard[^"]*)"', app_text or "")
        export_routes = [route for route in ai_dashboard_routes if "export" in route]
        post_blocks = re.findall(r'@app\.route\("([^"]+)"[^)]*methods=\[[^\]]*"POST"', app_text or "")
        checks = [
            {
                "name": "AI Dashboard 路由范围",
                "status": "ok" if all(route.startswith("/ai-dashboard") for route in ai_dashboard_routes) else "warning",
                "summary": f"当前识别 AI Dashboard 路由 {len(ai_dashboard_routes)} 条，均应保持权限保护。",
            },
            {
                "name": "导出路由集中度",
                "status": "ok" if all(route.startswith("/ai-dashboard/") for route in export_routes) else "risky",
                "summary": f"当前识别导出路由 {len(export_routes)} 条，建议持续集中在 /ai-dashboard/ 下。",
            },
            {
                "name": "任意文件下载风险",
                "status": "risky" if "/ai-dashboard/export-file" in app_text or "request.args.get(\"path\"" in app_text else "ok",
                "summary": "未识别到 /ai-dashboard/export-file 任意 path 下载接口。" if "/ai-dashboard/export-file" not in app_text else "存在 export-file/path 下载风险，需人工复查。",
            },
            {
                "name": "Dashboard POST 路由",
                "status": "warning" if post_blocks else "ok",
                "summary": f"识别到 {len(post_blocks)} 个 POST 路由，生产部署需逐项确认 CSRF、权限和审计。" if post_blocks else "未识别到 Dashboard 危险 POST 路由。",
            },
        ]
        return checks

    @classmethod
    def _build_export_file_security_checks(cls, app_text: str) -> list[dict]:
        files = cls._export_files()
        zip_files = [item for item in files if item.suffix.lower() == ".zip"]
        largest_zip = max((item.stat().st_size for item in zip_files if item.exists()), default=0)
        unsafe_names = [item.name for item in files if not re.match(r"^[\w.\-()\u4e00-\u9fff]+$", item.name)]
        return [
            {
                "name": "导出目录暴露方式",
                "status": "ok" if "/ai-dashboard/export-file" not in app_text else "risky",
                "summary": "导出目录仅用于服务端扫描展示，未识别到任意文件下载路由。" if "/ai-dashboard/export-file" not in app_text else "存在导出文件直接下载路由，需复查 path 限制。",
            },
            {
                "name": "任意 path 下载",
                "status": "risky" if "request.args.get(\"path\"" in app_text or "request.args.get('path'" in app_text else "ok",
                "summary": "未识别到 path 参数直取文件下载逻辑。",
            },
            {
                "name": "ZIP 体积风险",
                "status": "warning" if largest_zip > 500 * 1024 * 1024 else "ok",
                "summary": f"最大 ZIP 文件 {cls._format_size(largest_zip)}，超过 500MB 时建议拆分或限制保留。",
            },
            {
                "name": "文件命名安全",
                "status": "warning" if unsafe_names else "ok",
                "summary": f"发现 {len(unsafe_names)} 个可疑文件名。" if unsafe_names else "导出文件名未发现明显异常字符。",
            },
        ]

    @classmethod
    def _build_json_backup_checks(cls) -> list[dict]:
        checks = []
        for filename in cls.KEY_JSON_FILES:
            path = cls.DATA_DIR / filename
            backup_candidates = list(cls.DATA_DIR.glob(f"{filename}.*")) + list(cls.DATA_DIR.glob(f"{path.stem}*.bak"))
            if not path.exists():
                checks.append({"file": filename, "status": "warning", "summary": "关键 JSON 文件不存在，建议确认是否为首次运行并纳入备份。"})
                continue
            broken = False
            try:
                json.loads(path.read_text(encoding="utf-8") or "null")
            except Exception:
                broken = True
            if broken and not backup_candidates:
                status = "risky"
                summary = "JSON 文件损坏且未发现备份候选，建议人工备份后修复。"
            elif broken:
                status = "warning"
                summary = "JSON 文件损坏，已发现备份候选，建议人工核对恢复。"
            elif not backup_candidates:
                status = "warning"
                summary = "JSON 文件可读，但未发现备份候选，建议增加每日备份。"
            else:
                status = "ok"
                summary = "JSON 文件可读，并发现备份候选。"
            checks.append({"file": filename, "status": status, "summary": summary})
        return checks

    @staticmethod
    def _build_timeout_risk_checks(app_text: str) -> list[dict]:
        dashboard_route_count = len(re.findall(r'@app\.route\("/ai-dashboard', app_text or ""))
        export_route_count = len(re.findall(r'@app\.route\("/ai-dashboard[^"]*export', app_text or ""))
        return [
            {"name": "Dashboard 模块数量", "status": "warning" if dashboard_route_count > 80 else "ok", "summary": f"当前 Dashboard 路由约 {dashboard_route_count} 条，页面过重时建议继续拆分独立页。"},
            {"name": "导出报表数量", "status": "warning" if export_route_count > 50 else "ok", "summary": f"当前导出路由约 {export_route_count} 条，批量导出需关注超时。"},
            {"name": "批量导出耗时", "status": "warning", "summary": "批量导出应在生产环境设置超时、任务队列或分批策略。"},
            {"name": "Smoke Test 耗时", "status": "ok", "summary": "Smoke Test 为只读检查，建议定期运行并限制单次检查范围。"},
        ]

    @classmethod
    def _build_large_file_risk_checks(cls) -> list[dict]:
        export_files = cls._export_files()
        export_total = sum(item.stat().st_size for item in export_files if item.exists())
        json_files = list(cls.DATA_DIR.glob("*.json")) if cls.DATA_DIR.exists() else []
        largest_json = max((item.stat().st_size for item in json_files if item.exists()), default=0)
        return [
            {"name": "导出文件数量", "status": "risky" if len(export_files) > 2000 else ("warning" if len(export_files) > 500 else "ok"), "summary": f"导出目录当前约 {len(export_files)} 个文件。"},
            {"name": "导出目录总大小", "status": "risky" if export_total > 2 * 1024**3 else ("warning" if export_total > 500 * 1024**2 else "ok"), "summary": f"导出目录总大小约 {cls._format_size(export_total)}。"},
            {"name": "JSON 文件大小", "status": "warning" if largest_json > 50 * 1024 * 1024 else "ok", "summary": f"最大 JSON 文件约 {cls._format_size(largest_json)}。"},
        ]

    @staticmethod
    def _build_fallback_checks(app_text: str) -> list[dict]:
        return [
            {"name": "Smoke Test 兜底", "status": "ok" if "run_smoke_test" in app_text else "warning", "summary": "Smoke Test 路由可独立只读检查 Dashboard。"},
            {"name": "Ops Health 兜底", "status": "ok" if "build_ops_health_center" in app_text else "warning", "summary": "Ops Health 可聚合 JSON、路由、导出等健康状态。"},
            {"name": "Export Operations 兜底", "status": "ok" if "build_export_operations_center" in app_text else "warning", "summary": "Export Operations 可展示导出历史与失败项。"},
            {"name": "JSON Store 损坏兜底", "status": "warning", "summary": "建议生产环境补充 JSON 损坏时的备份恢复 SOP，当前仅生成检查建议。"},
        ]

    @staticmethod
    def _build_audit_log_suggestions() -> list[dict]:
        return [
            {"item": "登录访问审计", "status": "suggested", "summary": "记录管理员登录、失败登录和来源 IP。"},
            {"item": "导出操作审计", "status": "suggested", "summary": "记录导出类型、格式、操作者和耗时。"},
            {"item": "调度导出审计", "status": "suggested", "summary": "记录调度触发、通知结果和失败原因。"},
            {"item": "创建快照审计", "status": "suggested", "summary": "记录 Dashboard 快照生成时间与文件大小。"},
            {"item": "权限变更审计", "status": "suggested", "summary": "记录角色权限变更和操作者。"},
        ]

    @staticmethod
    def _build_deployment_checklist() -> list[dict]:
        return [
            {"item": "Nginx client_max_body_size", "status": "manual", "summary": "按导出 ZIP 体积设置上传/响应限制。"},
            {"item": "systemd restart policy", "status": "manual", "summary": "配置异常退出自动重启和启动超时。"},
            {"item": "data 目录备份", "status": "manual", "summary": "每日备份 data JSON 和导出历史。"},
            {"item": "SSL", "status": "manual", "summary": "生产环境必须启用 HTTPS。"},
            {"item": ".env 权限", "status": "manual", "summary": "限制环境变量文件读权限。"},
            {"item": "导出目录权限", "status": "manual", "summary": "导出目录不应被 Web 服务器直接静态暴露。"},
            {"item": "日志轮转", "status": "manual", "summary": "配置应用日志、Nginx 日志轮转。"},
            {"item": "RDS 连接检查", "status": "manual", "summary": "检查连接池、超时和慢查询日志。"},
        ]

    @staticmethod
    def _build_production_risks(route_checks: list[dict], export_checks: list[dict], json_checks: list[dict], timeout_checks: list[dict], large_checks: list[dict]) -> list[dict]:
        risks = []
        sources = [
            ("路由权限需复查", route_checks),
            ("导出文件安全风险", export_checks),
            ("JSON 未备份或损坏", json_checks),
            ("页面过重", timeout_checks),
            ("数据目录膨胀", large_checks),
        ]
        for title, checks in sources:
            bad = [item for item in checks if item.get("status") in {"warning", "risky"}]
            if bad:
                risks.append({"risk": title, "status": "risky" if any(item.get("status") == "risky" for item in bad) else "warning", "summary": bad[0].get("summary") or "需人工复查。"})
        risks.append({"risk": "通知未配置", "status": "warning", "summary": "建议生产环境配置 SMTP/Webhook，以便导出与运维异常及时通知。"})
        return risks[:8]

    @staticmethod
    def _resolve_status(permission_checks: list[dict], route_checks: list[dict], export_checks: list[dict], json_checks: list[dict], large_checks: list[dict], risks: list[dict]) -> str:
        all_checks = permission_checks + route_checks + export_checks + json_checks + large_checks + risks
        if any(item.get("status") == "risky" for item in all_checks):
            return "risky"
        if any(item.get("status") == "warning" for item in all_checks):
            return "warning"
        return "safe"

    @staticmethod
    def _build_summary(status: str, risks: list[dict]) -> str:
        if status == "risky":
            return f"AI Dashboard 生产级加固发现 {len(risks)} 类风险，需优先人工复查路由、导出与备份。"
        if status == "warning":
            return f"AI Dashboard 生产级加固发现 {len(risks)} 类关注项，建议部署前完成清单复核。"
        return "AI Dashboard 生产级加固未发现明显风险，建议保持定期检查。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        actions = [
            "定期备份 data JSON",
            "限制导出文件保留周期",
            "复查导出路由权限",
            "配置日志轮转",
            "配置 SMTP/Webhook",
            "定期运行 Smoke Test",
            "定期检查导出目录大小",
            "复查生产 Nginx/systemd 配置",
            "限制导出目录静态访问",
            "为关键路由补充访问审计",
        ]
        return actions if status in {"risky", "warning"} else actions[:7]

    @classmethod
    def _export_files(cls) -> list[Path]:
        if not cls.EXPORT_DIR.exists():
            return []
        return [item for item in cls.EXPORT_DIR.iterdir() if item.is_file()]

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size or 0)
        for unit in ["B", "KB", "MB", "GB"]:
            if value < 1024 or unit == "GB":
                return f"{value:.1f}{unit}"
            value /= 1024
        return f"{value:.1f}GB"

    @classmethod
    def build_production_hardening_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_production_hardening_center()
        lines = [
            "\u3010AI Dashboard \u751f\u4ea7\u7ea7\u52a0\u56fa\u3011",
            f"\u72b6\u6001\uff1a{center.get('hardening_status')}",
            center.get("summary") or "\u5f53\u524d\u6682\u65e0 Dashboard \u751f\u4ea7\u7ea7\u52a0\u56fa\u6570\u636e\u3002",
            "",
            "\u9ad8\u98ce\u9669\u7f3a\u53e3\uff1a",
        ]
        for item in center.get("high_risk_gaps") or []:
            lines.append(f"- {item.get('risk')} [{item.get('status')}] {item.get('summary')}")
        lines.append("")
        lines.append("\u63a8\u8350\u52a8\u4f5c\uff1a")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_production_hardening_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_production_hardening_center()
        lines = [
            "# AI Dashboard \u751f\u4ea7\u7ea7\u52a0\u56fa",
            "",
            f"- \u72b6\u6001\uff1a{center.get('hardening_status')}",
            f"- \u6458\u8981\uff1a{center.get('summary')}",
            "",
            "## \u9ad8\u98ce\u9669\u7f3a\u53e3",
        ]
        for item in center.get("high_risk_gaps") or []:
            lines.append(f"- **{item.get('risk')}** [{item.get('status')}]\uff1a{item.get('summary')}")
        lines.append("")
        lines.append("## \u90e8\u7f72\u68c0\u67e5")
        for item in center.get("deployment_checklist") or []:
            lines.append(f"- **{item.get('item')}**\uff1a{item.get('summary')}")
        return "\n".join(lines)

    @classmethod
    def build_production_hardening_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_production_hardening_center()
        rows = []
        groups = [
            ("安全检查清单", "security_checklist", "name"),
            ("Runtime 安全检查", "runtime_safety_checklist", "name"),
            ("导出系统安全检查", "export_safety_checklist", "name"),
            ("运维系统安全检查", "ops_safety_checklist", "name"),
            ("权限检查", "permission_checklist", "route"),
            ("路由加固检查", "route_hardening_checklist", "name"),
            ("JSON 文件加固检查", "json_file_hardening_checklist", "file"),
            ("模板加固检查", "template_hardening_checklist", "name"),
            ("部署检查", "deployment_checklist", "item"),
            ("高风险缺口", "high_risk_gaps", "risk"),
        ]
        for module, key, title_key in groups:
            for item in center.get(key) or []:
                rows.append({
                    "分类": module,
                    "检查项": item.get(title_key) or item.get("item") or "",
                    "状态": item.get("status") or "",
                    "风险等级": item.get("risk_level") or item.get("status") or "",
                    "是否需要人工处理": "是" if item.get("status") in {"warning", "risky", "manual", "manual_required", "critical"} else "否",
                    "说明": item.get("summary") or "",
                    "建议动作": item.get("suggestion") or "",
                })
        return rows

