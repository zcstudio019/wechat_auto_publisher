from __future__ import annotations

from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService
from services.ai_dashboard_production_hardening_service import AIDashboardProductionHardeningService
from services.ai_dashboard_release_readiness_service import AIDashboardReleaseReadinessService


class AIDashboardLaunchReadinessService:
    """Read-only launch readiness view for AI Dashboard."""

    @classmethod
    def build_launch_readiness_center(cls) -> dict:
        release = cls._safe_call(AIDashboardReleaseReadinessService.build_release_readiness_center)
        hardening = cls._safe_call(AIDashboardProductionHardeningService.build_production_hardening_center)
        ops = cls._safe_call(AIDashboardOpsHealthService.build_ops_health_center)
        export_ops = cls._safe_call(AIDashboardExportOperationsService.build_export_operations_center)

        blocking_issues = cls._normalize_checks(
            release.get("blocking_checks", []) or release.get("must_fix_before_release", []),
            default_category="上线阻塞",
            blocking=True,
        )
        route_readiness = cls._normalize_checks(hardening.get("route_hardening_checklist", []) or hardening.get("route_security_checks", []), "路由准备度")
        template_readiness = cls._normalize_checks(hardening.get("template_hardening_checklist", []), "模板准备度")
        permission_readiness = cls._normalize_checks(hardening.get("permission_checklist", []) or hardening.get("permission_checks", []), "权限准备度")
        data_file_readiness = cls._normalize_checks(hardening.get("json_file_hardening_checklist", []) or hardening.get("json_backup_checks", []), "数据文件准备度")
        deployment_readiness = cls._normalize_checks(hardening.get("deployment_checklist", []), "部署准备度")
        go_live_checklist = cls._normalize_checks(release.get("deployment_checklist", []) or release.get("go_live_checklist", []), "上线检查清单")

        readiness_status = cls._resolve_status(release, blocking_issues)
        readiness_score = cls._score(
            route_readiness
            + template_readiness
            + permission_readiness
            + data_file_readiness
            + deployment_readiness
            + blocking_issues
        )
        return {
            "readiness_status": readiness_status,
            "readiness_score": readiness_score,
            "summary": cls._summary(readiness_status, readiness_score, blocking_issues),
            "production_hardening_status": cls._status_summary(
                "生产级加固状态",
                hardening.get("hardening_status") or "unknown",
                hardening.get("summary") or "当前暂无生产级加固状态。",
            ),
            "runtime_safety_status": cls._status_summary(
                "Runtime 安全状态",
                cls._runtime_status(hardening, ops),
                "基于生产级加固、运维健康和运行时安全检查生成。",
            ),
            "ops_health_status": cls._status_summary(
                "运维健康状态",
                ops.get("health_status") or ops.get("ops_status") or "unknown",
                ops.get("summary") or "当前暂无运维健康状态。",
            ),
            "export_system_status": cls._status_summary(
                "导出系统状态",
                export_ops.get("operation_status") or export_ops.get("operations_status") or "unknown",
                export_ops.get("summary") or "当前暂无导出系统状态。",
            ),
            "route_readiness": route_readiness,
            "template_readiness": template_readiness,
            "permission_readiness": permission_readiness,
            "data_file_readiness": data_file_readiness,
            "deployment_readiness": deployment_readiness,
            "blocking_issues": blocking_issues,
            "go_live_checklist": go_live_checklist,
            "recommended_actions": release.get("recommended_actions") or cls._recommended_actions(readiness_status),
        }

    @staticmethod
    def _safe_call(fn) -> dict:
        try:
            value = fn()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"status": "failed", "summary": f"读取上线准备度依赖失败：{exc}"}

    @staticmethod
    def _status_summary(title: str, status: str, summary: str) -> dict:
        return {"title": title, "status": status or "unknown", "summary": summary or ""}

    @classmethod
    def _normalize_checks(cls, items, default_category: str, blocking: bool = False) -> list[dict]:
        checks = []
        for item in items or []:
            if isinstance(item, dict):
                title = item.get("name") or item.get("item") or item.get("route") or item.get("file") or item.get("risk") or default_category
                status = item.get("status") or ("blocking" if blocking else "manual_required")
                summary = item.get("summary") or item.get("message") or ""
                suggestion = item.get("suggestion") or item.get("recommended_action") or ""
            else:
                title = str(item)
                status = "blocking" if blocking else "manual_required"
                summary = str(item)
                suggestion = ""
            checks.append(
                {
                    "category": default_category,
                    "title": title,
                    "status": cls._normalize_status(status),
                    "readiness_score": cls._item_score(status),
                    "blocking": bool(blocking or cls._normalize_status(status) in {"blocking", "fail", "critical", "blocked"}),
                    "summary": summary,
                    "suggestion": suggestion,
                }
            )
        return checks

    @staticmethod
    def _normalize_status(status: str) -> str:
        value = str(status or "unknown").strip().lower()
        mapping = {
            "ok": "pass",
            "passed": "pass",
            "safe": "pass",
            "ready": "pass",
            "manual": "manual_required",
            "risky": "critical",
            "failed": "fail",
            "blocked": "blocking",
        }
        return mapping.get(value, value)

    @staticmethod
    def _item_score(status: str) -> int:
        value = AIDashboardLaunchReadinessService._normalize_status(status)
        if value == "pass":
            return 100
        if value in {"warning", "manual_required", "not_configured"}:
            return 70
        if value in {"missing", "attention"}:
            return 55
        if value in {"fail", "critical", "blocking"}:
            return 0
        return 60

    @staticmethod
    def _score(items: list[dict]) -> int:
        if not items:
            return 0
        score = sum(int(item.get("readiness_score") or 0) for item in items) // len(items)
        blocking_count = sum(1 for item in items if item.get("blocking"))
        return max(0, min(100, score - blocking_count * 10))

    @staticmethod
    def _resolve_status(release: dict, blocking_issues: list[dict]) -> str:
        release_status = str(release.get("release_status") or "").lower()
        if blocking_issues or release_status in {"blocked", "critical"}:
            return "blocked"
        if release_status in {"ready", "pass", "passed"}:
            return "ready"
        if release_status in {"conditional", "warning", "attention"}:
            return "attention"
        return "unknown"

    @staticmethod
    def _runtime_status(hardening: dict, ops: dict) -> str:
        hardening_status = str(hardening.get("hardening_status") or "").lower()
        ops_status = str(ops.get("health_status") or ops.get("ops_status") or "").lower()
        if hardening_status in {"risky", "critical"} or ops_status in {"critical", "failed"}:
            return "critical"
        if hardening_status in {"warning", "attention"} or ops_status in {"warning", "attention"}:
            return "warning"
        if hardening_status in {"safe", "healthy", "normal"} or ops_status in {"healthy", "normal"}:
            return "healthy"
        return "unknown"

    @staticmethod
    def _summary(status: str, score: int, blocking_issues: list[dict]) -> str:
        if status == "ready":
            return f"上线准备度通过，当前评分 {score}，可进入上线窗口。"
        if status == "blocked":
            return f"上线准备度存在阻塞，当前评分 {score}，需先处理 {len(blocking_issues)} 个阻塞问题。"
        if status == "attention":
            return f"上线准备度需关注，当前评分 {score}，建议人工复核后再上线。"
        return "当前暂无 Dashboard 上线准备度数据。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "ready":
            return ["创建上线 tag", "备份 data 目录", "执行最终 py_compile 与 unittest", "确认回滚说明"]
        if status == "blocked":
            return ["优先处理阻塞问题", "修复后重新运行上线准备度检查", "确认生产级加固和运维健康状态"]
        return ["补齐上线准备度数据", "复核路由、权限、模板和数据文件状态"]

    @classmethod
    def build_launch_readiness_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_launch_readiness_center()
        lines = [
            "【AI Dashboard 上线准备度中心】",
            f"状态：{center.get('readiness_status')}",
            f"评分：{center.get('readiness_score')}",
            center.get("summary") or "",
            "",
            "阻塞问题：",
        ]
        for item in center.get("blocking_issues") or []:
            lines.append(f"- {item.get('title')}：{item.get('summary')}")
        lines.append("")
        lines.append("推荐处理动作：")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_launch_readiness_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_launch_readiness_center()
        rows = []
        groups = [
            ("路由准备度", "route_readiness"),
            ("模板准备度", "template_readiness"),
            ("权限准备度", "permission_readiness"),
            ("数据文件准备度", "data_file_readiness"),
            ("部署准备度", "deployment_readiness"),
            ("阻塞问题", "blocking_issues"),
            ("上线检查清单", "go_live_checklist"),
        ]
        for category, key in groups:
            for item in center.get(key) or []:
                rows.append(
                    {
                        "分类": category,
                        "检查项": item.get("title") or "",
                        "状态": item.get("status") or "",
                        "准备度评分": item.get("readiness_score") or 0,
                        "是否阻塞上线": "是" if item.get("blocking") else "否",
                        "说明": item.get("summary") or "",
                        "建议动作": item.get("suggestion") or "",
                    }
                )
        return rows
