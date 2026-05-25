"""AI Dashboard 运维健康中心只读服务。"""

from __future__ import annotations

import json
from pathlib import Path

from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_smoke_test_service import AIDashboardSmokeTestService


class AIDashboardOpsHealthService:
    """构建 Dashboard 自身的运维健康诊断。"""

    DATA_DIR = Path(__file__).resolve().parents[1] / "data"
    EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "ai_dashboard_exports"
    STORAGE_WARNING_BYTES = 500 * 1024 * 1024
    STORAGE_CRITICAL_BYTES = 2 * 1024 * 1024 * 1024

    JSON_FILES = [
        "ai_dashboard_export_history.json",
        "ai_dashboard_snapshot.json",
        "ai_runtime_alerts.json",
        "ai_runtime_incidents.json",
        "ai_runtime_postmortems.json",
        "ai_runtime_learning.json",
        "ai_runtime_knowledge_sync.json",
        "ai_runtime_feedback_loop.json",
        "ai_runtime_evolution_history.json",
        "ai_runtime_snapshots.json",
        "ai_approval_pipeline.json",
        "ai_memory_center.json",
        "ai_knowledge_base.json",
        "ai_sop_center.json",
    ]

    @classmethod
    def build_ops_health_center(cls) -> dict:
        smoke_raw = AIDashboardSmokeTestService.run_smoke_test()
        export_ops = AIDashboardExportOperationsService.build_export_operations_center()
        smoke_status = cls._build_smoke_test_status(smoke_raw)
        json_health = cls._build_json_health()
        export_storage = cls._build_export_storage()
        route_health = cls._extract_check_health(smoke_raw, ("route", "路由", "导出"))
        template_health = cls._extract_check_health(smoke_raw, ("template", "模板", "标题"))
        runtime_key_health = cls._extract_check_health(smoke_raw, ("runtime key", "Runtime key"))
        export_status = cls._build_export_operations_status(export_ops)
        runtime_status = cls._build_component_status(runtime_key_health, "Runtime 模块状态")
        route_status = cls._build_component_status(route_health, "路由注册状态")
        template_status = cls._build_component_status(template_health, "模板渲染状态")
        json_file_status = cls._build_json_file_status(json_health)
        scheduler_status = cls._build_scheduler_status(export_status)

        ops_risks = cls._build_ops_risks(
            smoke_status,
            export_status,
            json_health,
            export_storage,
            route_health,
            template_health,
            runtime_key_health,
        )
        ops_status = cls._resolve_ops_status(
            smoke_status,
            json_health,
            export_storage,
            route_health,
            template_health,
            runtime_key_health,
            export_status,
        )
        health_score = cls._build_health_score(ops_status, ops_risks, json_health)
        warning_items = cls._build_warning_items(
            smoke_status,
            export_status,
            json_health,
            export_storage,
            route_health,
            template_health,
            runtime_key_health,
        )
        recommended_actions = cls._build_recommended_actions(ops_risks, smoke_status, export_status, json_health, export_storage)
        summary = cls._build_summary(ops_status, ops_risks)

        return {
            "health_status": ops_status,
            "health_score": health_score,
            "ops_status": ops_status,
            "summary": summary,
            "runtime_status": runtime_status,
            "export_status": export_status,
            "scheduler_status": scheduler_status,
            "json_file_status": json_file_status,
            "route_status": route_status,
            "template_status": template_status,
            "smoke_test_status": smoke_status,
            "export_operations_status": export_status,
            "json_health": json_health,
            "export_storage": export_storage,
            "route_health": route_health,
            "template_health": template_health,
            "runtime_key_health": runtime_key_health,
            "warning_items": warning_items,
            "risk_items": ops_risks,
            "ops_risks": ops_risks,
            "recommended_actions": recommended_actions,
        }

    @staticmethod
    def _build_smoke_test_status(smoke_raw: dict) -> dict:
        smoke_raw = smoke_raw or {}
        failed_checks = list(smoke_raw.get("failed_checks") or [])
        warning_checks = list(smoke_raw.get("warning_checks") or [])
        failed_count = smoke_raw.get("failed_count")
        warning_count = smoke_raw.get("warning_count")
        return {
            "status": smoke_raw.get("status") or "warning",
            "failed_count": len(failed_checks) if failed_count is None else int(failed_count or 0),
            "warning_count": len(warning_checks) if warning_count is None else int(warning_count or 0),
            "summary": smoke_raw.get("summary") or "暂无 Smoke Test 摘要。",
        }

    @classmethod
    def _build_export_operations_status(cls, export_ops: dict) -> dict:
        export_ops = export_ops or {}
        operations_status = export_ops.get("operations_status") or export_ops.get("operation_status") or "warning"
        return {
            "status": operations_status,
            "operations_status": operations_status,
            "latest_export_result": export_ops.get("latest_export_result") or {},
            "scheduler_history": list(export_ops.get("scheduler_history") or export_ops.get("schedule_history") or [])[:7],
            "notification_status": export_ops.get("notification_status") or {},
            "failed_items": list(export_ops.get("failed_items") or []),
            "warnings": list(export_ops.get("warnings") or []),
        }

    @staticmethod
    def _build_component_status(items: list[dict], label: str) -> dict:
        items = list(items or [])
        if not items:
            return {
                "status": "unknown",
                "label": label,
                "total": 0,
                "ok_count": 0,
                "warning_count": 0,
                "failed_count": 0,
                "summary": "暂无检查数据。",
            }
        failed_count = sum(1 for item in items if item.get("status") in {"failed", "critical", "broken"})
        warning_count = sum(1 for item in items if item.get("status") in {"warning", "missing"})
        ok_count = sum(1 for item in items if item.get("status") in {"ok", "passed", "success", "healthy", "normal"})
        if failed_count:
            status = "failed"
        elif warning_count:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "label": label,
            "total": len(items),
            "ok_count": ok_count,
            "warning_count": warning_count,
            "failed_count": failed_count,
            "summary": f"共 {len(items)} 项，失败 {failed_count} 项，警告 {warning_count} 项。",
        }

    @staticmethod
    def _build_json_file_status(json_health: list[dict]) -> dict:
        status = AIDashboardOpsHealthService._build_component_status(json_health, "JSON 文件状态")
        status["missing_count"] = sum(1 for item in json_health or [] if item.get("status") == "missing")
        status["broken_count"] = sum(1 for item in json_health or [] if item.get("status") == "broken")
        return status

    @staticmethod
    def _build_scheduler_status(export_status: dict) -> dict:
        history = list((export_status or {}).get("scheduler_history") or [])
        latest = history[0] if history else {}
        notification = (export_status or {}).get("notification_status") or {}
        if latest.get("status") == "failed":
            status = "failed"
        elif not history:
            status = "not_configured"
        elif (export_status or {}).get("warnings"):
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "latest": latest,
            "history_count": len(history),
            "email_enabled": bool(notification.get("email_enabled")),
            "webhook_enabled": bool(notification.get("webhook_enabled")),
            "summary": "调度历史正常。" if status == "ok" else "调度导出需要关注。",
        }

    @classmethod
    def _build_json_health(cls) -> list[dict]:
        results = []
        for filename in cls.JSON_FILES:
            path = cls.DATA_DIR / filename
            if not path.exists():
                results.append({
                    "file": filename,
                    "status": "missing",
                    "summary": "文件不存在，按空历史处理。",
                })
                continue
            try:
                text = path.read_text(encoding="utf-8")
                if text.strip():
                    json.loads(text)
            except Exception as exc:
                results.append({
                    "file": filename,
                    "status": "broken",
                    "summary": f"JSON 读取或解析失败：{exc}",
                })
                continue
            results.append({
                "file": filename,
                "status": "ok",
                "summary": "JSON 文件可读且格式正常。",
            })
        return results

    @classmethod
    def _build_export_storage(cls) -> dict:
        if not cls.EXPORT_DIR.exists() or not cls.EXPORT_DIR.is_dir():
            return {
                "file_count": 0,
                "total_size": "0 B",
                "latest_file": "",
                "storage_status": "ok",
            }

        file_count = 0
        total_bytes = 0
        latest_file = ""
        latest_time = 0.0
        for path in cls.EXPORT_DIR.iterdir():
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            file_count += 1
            total_bytes += stat.st_size
            if stat.st_ctime > latest_time:
                latest_time = stat.st_ctime
                latest_file = path.name

        if file_count > 2000 or total_bytes > cls.STORAGE_CRITICAL_BYTES:
            storage_status = "critical"
        elif file_count > 500 or total_bytes > cls.STORAGE_WARNING_BYTES:
            storage_status = "warning"
        else:
            storage_status = "ok"

        return {
            "file_count": file_count,
            "total_size": cls._format_size(total_bytes),
            "latest_file": latest_file,
            "storage_status": storage_status,
        }

    @staticmethod
    def _extract_check_health(smoke_raw: dict, keywords: tuple[str, ...]) -> list[dict]:
        checks = list((smoke_raw or {}).get("checks") or [])
        results = []
        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        for check in checks:
            name = str(check.get("name") or "")
            summary = str(check.get("summary") or "")
            haystack = f"{name} {summary}".lower()
            if not any(keyword in haystack for keyword in lowered_keywords):
                continue
            results.append({
                "name": name or "未命名检查",
                "status": check.get("status") or "warning",
                "summary": summary or "-",
            })
        return results

    @staticmethod
    def _has_failed(items: list[dict]) -> bool:
        return any(item.get("status") in ("failed", "critical", "broken") for item in items or [])

    @staticmethod
    def _has_warning(items: list[dict]) -> bool:
        return any(item.get("status") in ("warning", "missing") for item in items or [])

    @classmethod
    def _resolve_ops_status(
        cls,
        smoke_status: dict,
        json_health: list[dict],
        export_storage: dict,
        route_health: list[dict],
        template_health: list[dict],
        runtime_key_health: list[dict],
        export_status: dict,
    ) -> str:
        if smoke_status.get("status") == "failed":
            return "critical"
        if cls._has_failed(runtime_key_health) or cls._has_failed(route_health) or cls._has_failed(template_health):
            return "warning"

        latest_schedule = (export_status.get("scheduler_history") or [{}])[0] if export_status.get("scheduler_history") else {}
        notifications = export_status.get("notification_status") or {}
        notification_missing = not notifications.get("email_enabled") or not notifications.get("webhook_enabled")
        if (
            smoke_status.get("status") == "warning"
            or any(item.get("status") == "broken" for item in json_health)
            or export_storage.get("storage_status") in ("warning", "critical")
            or latest_schedule.get("status") == "failed"
            or notification_missing
            or export_status.get("failed_items")
            or export_status.get("warnings")
        ):
            return "warning"
        return "healthy"

    @staticmethod
    def _build_health_score(ops_status: str, ops_risks: list[dict], json_health: list[dict]) -> int:
        score = 100
        for item in ops_risks or []:
            level = item.get("level")
            if level == "critical":
                score -= 20
            elif level in {"warning", "failed"}:
                score -= 10
            else:
                score -= 5
        score -= 5 * sum(1 for item in json_health or [] if item.get("status") == "broken")
        if ops_status == "unknown":
            score -= 10
        return max(0, min(100, score))

    @classmethod
    def _build_warning_items(
        cls,
        smoke_status: dict,
        export_status: dict,
        json_health: list[dict],
        export_storage: dict,
        route_health: list[dict],
        template_health: list[dict],
        runtime_key_health: list[dict],
    ) -> list[dict]:
        warnings = []
        if smoke_status.get("warning_count"):
            warnings.append({"title": "冒烟测试存在警告", "status": "warning", "summary": smoke_status.get("summary") or ""})
        for item in json_health or []:
            if item.get("status") in {"missing", "broken"}:
                warnings.append({"title": item.get("file") or "JSON 文件", "status": item.get("status"), "summary": item.get("summary") or ""})
        if export_storage.get("storage_status") in {"warning", "critical"}:
            warnings.append({"title": "导出文件存储需关注", "status": export_storage.get("storage_status"), "summary": f"{export_storage.get('file_count') or 0} 个文件，{export_storage.get('total_size') or '0 B'}"})
        for group_name, items in (("路由检查", route_health), ("模板检查", template_health), ("运行时模块检查", runtime_key_health)):
            for item in items or []:
                if item.get("status") in {"warning", "missing", "failed", "critical", "broken"}:
                    warnings.append({"title": group_name, "status": item.get("status"), "summary": item.get("summary") or item.get("name") or ""})
        for item in (export_status or {}).get("warnings") or []:
            warnings.append({"title": "导出运营警告", "status": "warning", "summary": item})
        return warnings[:20]

    @classmethod
    def _build_ops_risks(
        cls,
        smoke_status: dict,
        export_status: dict,
        json_health: list[dict],
        export_storage: dict,
        route_health: list[dict],
        template_health: list[dict],
        runtime_key_health: list[dict],
    ) -> list[dict]:
        risks = []
        if cls._has_failed(runtime_key_health) or cls._has_failed(template_health):
            risks.append({"risk": "页面模块缺失风险", "level": "critical", "summary": "Runtime key 或模板标题存在缺失。"})
        if cls._has_failed(route_health):
            risks.append({"risk": "导出路由缺失风险", "level": "critical", "summary": "关键导出路由检查未通过。"})
        broken_json = [item["file"] for item in json_health if item.get("status") == "broken"]
        if broken_json:
            risks.append({"risk": "JSON 损坏风险", "level": "warning", "summary": "损坏文件：" + "、".join(broken_json[:5])})
        if export_storage.get("storage_status") in ("warning", "critical"):
            risks.append({"risk": "导出文件膨胀风险", "level": export_storage.get("storage_status"), "summary": f"当前 {export_storage.get('file_count')} 个文件，总大小 {export_storage.get('total_size')}。"})
        latest_schedule = (export_status.get("scheduler_history") or [{}])[0] if export_status.get("scheduler_history") else {}
        if latest_schedule.get("status") == "failed":
            risks.append({"risk": "调度失败风险", "level": "warning", "summary": latest_schedule.get("message") or "最近调度导出失败。"})
        notifications = export_status.get("notification_status") or {}
        if not notifications.get("email_enabled") or not notifications.get("webhook_enabled"):
            risks.append({"risk": "通知未配置风险", "level": "warning", "summary": "邮件或 Webhook 通知未完整配置。"})
        if smoke_status.get("status") == "failed":
            risks.append({"risk": "Smoke Test 失败风险", "level": "critical", "summary": smoke_status.get("summary") or "冒烟测试失败。"})
        elif smoke_status.get("status") == "warning":
            risks.append({"risk": "Smoke Test 警告风险", "level": "warning", "summary": smoke_status.get("summary") or "冒烟测试存在警告。"})
        return risks

    @staticmethod
    def _build_recommended_actions(
        ops_risks: list[dict],
        smoke_status: dict,
        export_status: dict,
        json_health: list[dict],
        export_storage: dict,
    ) -> list[str]:
        actions = []
        if smoke_status.get("status") == "failed":
            actions.append("先修复 Smoke Test 失败项")
        if export_storage.get("storage_status") in ("warning", "critical"):
            actions.append("清理旧导出文件")
        if any(item.get("status") == "broken" for item in json_health):
            actions.append("检查损坏 JSON")
        notifications = export_status.get("notification_status") or {}
        if not notifications.get("email_enabled") or not notifications.get("webhook_enabled"):
            actions.append("配置邮件或 Webhook 通知")
        latest_schedule = (export_status.get("scheduler_history") or [{}])[0] if export_status.get("scheduler_history") else {}
        if latest_schedule.get("status") == "failed":
            actions.append("检查导出调度失败原因")
        actions.append("定期运行冒烟测试")
        actions.append("保持 Dashboard key/title/route 测试")
        if not ops_risks:
            actions.append("维持当前 Dashboard 运维巡检节奏")
        return actions[:8]

    @staticmethod
    def _build_summary(ops_status: str, ops_risks: list[dict]) -> str:
        if ops_status == "critical":
            critical_count = sum(1 for item in ops_risks if item.get("level") == "critical")
            return f"Dashboard 运维健康存在 {critical_count} 个关键风险，请优先修复阻断项。"
        if ops_status == "warning":
            return f"Dashboard 运维健康存在 {len(ops_risks)} 个需关注风险，建议按优先级处理。"
        return "Dashboard 运维健康状态良好，关键检查未发现风险。"

    @staticmethod
    def _format_size(size: int) -> str:
        size = max(0, int(size or 0))
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

    @staticmethod
    def build_ops_health_text(center: dict | None = None) -> str:
        center = center or AIDashboardOpsHealthService.build_ops_health_center()
        lines = [
            "【AI Dashboard 运维健康中心】",
            "",
            f"运维状态：{center.get('ops_status') or 'warning'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "Smoke Test：",
        ]
        smoke = center.get("smoke_test_status") or {}
        lines.extend([
            f"- 状态：{smoke.get('status') or '-'}",
            f"- 失败数：{smoke.get('failed_count') or 0}",
            f"- 警告数：{smoke.get('warning_count') or 0}",
            f"- 摘要：{smoke.get('summary') or '-'}",
            "",
            "建议动作：",
        ])
        for index, action in enumerate(center.get("recommended_actions") or [], start=1):
            lines.append(f"{index}. {action}")
        return "\n".join(lines)

    @staticmethod
    def build_ops_health_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardOpsHealthService.build_ops_health_center()
        rows = []

        def add(module: str, obj: str, status: str, summary: str, suggestion: str = ""):
            rows.append({
                "模块": module,
                "对象": obj,
                "状态": status,
                "摘要": summary,
                "建议": suggestion,
            })

        add("Ops Health", "summary", center.get("ops_status") or "", center.get("summary") or "")
        smoke = center.get("smoke_test_status") or {}
        add("Smoke Test", "run_smoke_test", smoke.get("status") or "", smoke.get("summary") or "")
        export_storage = center.get("export_storage") or {}
        add("Export Storage", "data/ai_dashboard_exports", export_storage.get("storage_status") or "", f"{export_storage.get('file_count') or 0} files / {export_storage.get('total_size') or '0 B'}")
        for item in center.get("json_health") or []:
            add("JSON Health", item.get("file") or "", item.get("status") or "", item.get("summary") or "")
        for module, key in (("Route Health", "route_health"), ("Template Health", "template_health"), ("Runtime Key Health", "runtime_key_health")):
            for item in center.get(key) or []:
                add(module, item.get("name") or "", item.get("status") or "", item.get("summary") or "")
        for item in center.get("ops_risks") or []:
            add("Ops Risk", item.get("risk") or "", item.get("level") or "", item.get("summary") or "", "；".join(center.get("recommended_actions") or []))
        return rows
