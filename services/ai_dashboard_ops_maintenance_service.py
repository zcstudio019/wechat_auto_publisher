"""Read-only AI Dashboard operations maintenance plan center."""

from __future__ import annotations

from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService


class AIDashboardOpsMaintenanceService:
    """Build a maintenance plan from Dashboard ops health diagnostics."""

    WATCH_MODULES = [
        "Smoke Test",
        "Export Operations",
        "Runtime Snapshot",
        "Runtime Timeline",
        "Runtime Forecast",
        "Runtime Constitution",
        "Runtime Boundary",
        "Runtime Executive Dashboard",
    ]

    @classmethod
    def build_maintenance_plan(cls) -> dict:
        health = AIDashboardOpsHealthService.build_ops_health_center()
        maintenance_status = cls._resolve_maintenance_status(health)
        today_tasks = cls._build_today_tasks(health, maintenance_status)
        weekly_tasks = cls._build_weekly_tasks(health)
        cleanup_suggestions = cls._build_cleanup_suggestions(health)
        json_repair_suggestions = cls._build_json_repair_suggestions(health)
        archive_suggestions = cls._build_export_archive_suggestions(health)
        test_priorities = cls._build_test_priority(health)
        module_watchlist = cls._build_module_watchlist(health)
        risk_handling_sequence = cls._build_risk_handling_sequence(health)
        recommended_actions = cls._build_recommended_actions(
            today_tasks,
            cleanup_suggestions,
            json_repair_suggestions,
            archive_suggestions,
            test_priorities,
        )
        summary = cls._build_summary(maintenance_status, today_tasks, health)

        return {
            "maintenance_status": maintenance_status,
            "summary": summary,
            "today_tasks": today_tasks,
            "weekly_tasks": weekly_tasks,
            "cleanup_suggestions": cleanup_suggestions,
            "json_repair_suggestions": json_repair_suggestions,
            "archive_suggestions": archive_suggestions,
            "test_priorities": test_priorities,
            "module_watchlist": module_watchlist,
            "risk_handling_sequence": risk_handling_sequence,
            "recommended_actions": recommended_actions,
            "export_archive_suggestions": archive_suggestions,
            "test_priority": test_priorities,
        }

    @classmethod
    def _resolve_maintenance_status(cls, health: dict) -> str:
        ops_status = (health or {}).get("ops_status") or (health or {}).get("health_status")
        smoke = (health or {}).get("smoke_test_status") or {}
        if ops_status == "critical" or smoke.get("status") == "failed":
            return "critical"
        if cls._has_failed((health or {}).get("runtime_key_health") or []):
            return "critical"
        if cls._has_failed((health or {}).get("template_health") or []):
            return "critical"
        if cls._has_failed((health or {}).get("route_health") or []):
            return "critical"

        export_status = (health or {}).get("export_operations_status") or (health or {}).get("export_status") or {}
        latest_schedule = (export_status.get("scheduler_history") or [{}])[0] if export_status.get("scheduler_history") else {}
        notifications = export_status.get("notification_status") or {}
        if (
            ops_status == "warning"
            or any(item.get("status") in {"broken", "missing"} for item in (health or {}).get("json_health") or [])
            or ((health or {}).get("export_storage") or {}).get("storage_status") in {"warning", "critical"}
            or latest_schedule.get("status") == "failed"
            or not notifications.get("email_enabled")
            or not notifications.get("webhook_enabled")
            or export_status.get("warnings")
            or export_status.get("failed_items")
        ):
            return "attention"
        return "normal"

    @staticmethod
    def _has_failed(items: list[dict]) -> bool:
        return any(item.get("status") in {"failed", "critical", "broken"} for item in items or [])

    @staticmethod
    def _task(task: str, priority: str, reason: str) -> dict:
        return {"task": task, "priority": priority, "reason": reason}

    @classmethod
    def _build_today_tasks(cls, health: dict, maintenance_status: str) -> list[dict]:
        tasks = []
        smoke = (health or {}).get("smoke_test_status") or {}
        export_status = (health or {}).get("export_operations_status") or (health or {}).get("export_status") or {}
        export_storage = (health or {}).get("export_storage") or {}
        latest_schedule = (export_status.get("scheduler_history") or [{}])[0] if export_status.get("scheduler_history") else {}
        notifications = export_status.get("notification_status") or {}

        if smoke.get("status") == "failed":
            tasks.append(cls._task("检查 Smoke Test 失败项", "critical", smoke.get("summary") or "冒烟测试失败。"))
        elif smoke.get("status") == "warning":
            tasks.append(cls._task("复查 Smoke Test 警告项", "high", smoke.get("summary") or "冒烟测试存在警告。"))
        if latest_schedule.get("status") == "failed":
            tasks.append(cls._task("检查导出调度失败", "high", latest_schedule.get("message") or "最近调度导出失败。"))
        broken_json = [item for item in (health or {}).get("json_health") or [] if item.get("status") == "broken"]
        if broken_json:
            tasks.append(cls._task("检查损坏 JSON", "high", "损坏文件：" + "、".join(item.get("file") or "" for item in broken_json[:5])))
        missing_json = [item for item in (health or {}).get("json_health") or [] if item.get("status") == "missing"]
        if missing_json:
            tasks.append(cls._task("确认缺失 JSON 是否为首次运行兜底", "medium", "缺失文件：" + "、".join(item.get("file") or "" for item in missing_json[:5])))
        if export_storage.get("storage_status") in {"warning", "critical"}:
            tasks.append(cls._task("检查导出文件过大", "high", f"{export_storage.get('file_count') or 0} 个文件，总大小 {export_storage.get('total_size') or '0 B'}。"))
        if not notifications.get("email_enabled") or not notifications.get("webhook_enabled"):
            tasks.append(cls._task("检查通知配置", "medium", "邮件或 Webhook 通知未完整配置。"))
        if not tasks:
            tasks.append(cls._task("完成 Dashboard 只读巡检", "normal", "当前无明显维护风险。"))
        return tasks[:8]

    @staticmethod
    def _build_weekly_tasks(health: dict) -> list[dict]:
        return [
            {"task": "运行全量测试", "priority": "high", "reason": "确认 Dashboard、导出、健康检查与文章健康服务未回归。"},
            {"task": "复查 Runtime key/title/route 完整性", "priority": "high", "reason": "防止新增 Dashboard 模块后入口缺失。"},
            {"task": "归档导出报表", "priority": "medium", "reason": "降低导出目录膨胀和手工查找成本。"},
            {"task": "复查快照/时间轴数据", "priority": "medium", "reason": "确认 Runtime Snapshot 与 Timeline 数据可读。"},
            {"task": "检查 JSON 文件增长情况", "priority": "medium", "reason": "提前发现异常增长或损坏风险。"},
        ]

    @staticmethod
    def _build_cleanup_suggestions(health: dict) -> list[dict]:
        storage = (health or {}).get("export_storage") or {}
        priority = "high" if storage.get("storage_status") in {"warning", "critical"} else "medium"
        return [
            {"suggestion": "清理旧导出文件", "priority": priority, "reason": "仅建议人工清理，不自动删除文件。"},
            {"suggestion": "压缩归档历史 ZIP", "priority": "medium", "reason": "把历史报表集中归档，保留可追溯路径。"},
            {"suggestion": "保留最近 30 天导出", "priority": "medium", "reason": "降低导出目录容量压力。"},
            {"suggestion": "定期备份 data JSON", "priority": "medium", "reason": "避免健康数据和运行历史丢失。"},
        ]

    @staticmethod
    def _build_json_repair_suggestions(health: dict) -> list[dict]:
        json_health = (health or {}).get("json_health") or []
        broken = [item for item in json_health if item.get("status") == "broken"]
        missing = [item for item in json_health if item.get("status") == "missing"]
        priority = "high" if broken else ("medium" if missing else "normal")
        return [
            {"suggestion": "备份损坏 JSON", "priority": priority, "reason": "修复前先保留原始文件，便于回溯。"},
            {"suggestion": "用默认结构重建", "priority": priority, "reason": "仅作为人工修复建议，不自动写入。"},
            {"suggestion": "检查写入来源", "priority": "medium", "reason": "定位 JSON 损坏或缺失是否来自并发写入。"},
            {"suggestion": "增加 JsonStore 统一写入", "priority": "medium", "reason": "减少分散文件写入带来的格式风险。"},
        ]

    @staticmethod
    def _build_export_archive_suggestions(health: dict) -> list[dict]:
        return [
            {"suggestion": "每日导出归档", "priority": "medium", "reason": "按日期保留报表便于检索。"},
            {"suggestion": "每周 ZIP 归档", "priority": "medium", "reason": "把周报表打包为单一归档。"},
            {"suggestion": "每月清理", "priority": "medium", "reason": "控制导出目录长期增长。"},
            {"suggestion": "下载离线备份", "priority": "medium", "reason": "保留关键运维报表的离线副本。"},
        ]

    @staticmethod
    def _build_test_priority(health: dict) -> list[dict]:
        smoke = (health or {}).get("smoke_test_status") or {}
        export_status = (health or {}).get("export_operations_status") or {}
        return [
            {"test": "smoke test", "priority": "critical" if smoke.get("status") == "failed" else "high", "reason": "先确认 Dashboard 基础健康。"},
            {"test": "export operations test", "priority": "high" if export_status.get("failed_items") else "medium", "reason": "覆盖导出历史、调度与通知状态。"},
            {"test": "ops health test", "priority": "high", "reason": "确保运维健康中心判断稳定。"},
            {"test": "article health service test", "priority": "medium", "reason": "确认 Dashboard 数据源未回归。"},
            {"test": "full unittest", "priority": "medium", "reason": "最终做全量回归。"},
        ]

    @classmethod
    def _build_module_watchlist(cls, health: dict) -> list[dict]:
        risks = list((health or {}).get("ops_risks") or (health or {}).get("risk_items") or [])
        risk_text = "；".join(str(item.get("risk") or item.get("summary") or "") for item in risks)
        items = []
        for module in cls.WATCH_MODULES:
            priority = "high" if module in {"Smoke Test", "Export Operations"} and risk_text else "medium"
            items.append({
                "module": module,
                "priority": priority,
                "reason": "运维健康中心核心观察模块。" if priority == "high" else "每周巡检观察模块。",
            })
        return items

    @staticmethod
    def _build_risk_handling_sequence(health: dict) -> list[dict]:
        return [
            {"step": 1, "action": "先处理严重风险", "priority": "critical", "reason": "阻断类健康问题优先处理。"},
            {"step": 2, "action": "再修 warning", "priority": "high", "reason": "降低 Dashboard 运维风险继续扩散。"},
            {"step": 3, "action": "再处理 JSON", "priority": "high", "reason": "保证历史、快照和健康数据可读。"},
            {"step": 4, "action": "再处理导出存储", "priority": "medium", "reason": "控制导出目录文件数量和容量。"},
            {"step": 5, "action": "最后做归档和优化", "priority": "medium", "reason": "整理长期运维资产。"},
        ]

    @staticmethod
    def _build_recommended_actions(
        today_tasks: list[dict],
        cleanup_suggestions: list[dict],
        json_repair_suggestions: list[dict],
        export_archive_suggestions: list[dict],
        test_priority: list[dict],
    ) -> list[str]:
        actions = []
        actions.extend(item.get("task") for item in today_tasks if item.get("priority") in {"critical", "high"})
        actions.extend(item.get("suggestion") for item in json_repair_suggestions if item.get("priority") in {"critical", "high"})
        actions.extend(item.get("suggestion") for item in cleanup_suggestions[:2])
        actions.extend(item.get("suggestion") for item in export_archive_suggestions[:2])
        actions.extend(item.get("test") for item in test_priority[:2])
        safe_actions = []
        for action in actions:
            if action and action not in safe_actions:
                safe_actions.append(action)
        return safe_actions[:8]

    @staticmethod
    def _build_summary(status: str, today_tasks: list[dict], health: dict) -> str:
        if status in {"critical", "urgent"}:
            return f"Dashboard 运维维护计划处于紧急状态，今日需优先处理 {len(today_tasks)} 项任务。"
        if status == "attention":
            return f"Dashboard 运维维护计划需要关注，今日建议处理 {len(today_tasks)} 项任务。"
        return "Dashboard 运维维护计划正常，按周巡检和归档节奏维护即可。"

    @staticmethod
    def build_maintenance_text(plan: dict | None = None) -> str:
        plan = plan or AIDashboardOpsMaintenanceService.build_maintenance_plan()
        lines = [
            "【AI Dashboard 运维维护计划中心】",
            "",
            f"维护状态：{plan.get('maintenance_status') or 'normal'}",
            f"摘要：{plan.get('summary') or '-'}",
            "",
            "今日维护任务：",
        ]
        for index, item in enumerate(plan.get("today_tasks") or [], start=1):
            lines.append(f"{index}. [{item.get('priority') or '-'}] {item.get('task') or '-'} - {item.get('reason') or '-'}")
        lines.extend(["", "推荐动作："])
        for index, action in enumerate(plan.get("recommended_actions") or [], start=1):
            lines.append(f"{index}. {action}")
        return "\n".join(lines)

    @staticmethod
    def build_maintenance_rows(plan: dict | None = None) -> list[dict]:
        plan = plan or AIDashboardOpsMaintenanceService.build_maintenance_plan()
        rows = []

        def add(module: str, task: str, priority: str, reason: str, action: str = ""):
            rows.append({
                "模块": module,
                "任务/建议": task,
                "优先级": priority,
                "原因": reason,
                "建议动作": action,
            })

        add("维护计划", "维护摘要", plan.get("maintenance_status") or "", plan.get("summary") or "")
        for key, module, field in (
            ("today_tasks", "今日维护任务", "task"),
            ("weekly_tasks", "本周维护任务", "task"),
            ("cleanup_suggestions", "文件清理建议", "suggestion"),
            ("json_repair_suggestions", "JSON 修复建议", "suggestion"),
            ("archive_suggestions", "导出归档建议", "suggestion"),
            ("test_priorities", "测试优先级", "test"),
            ("module_watchlist", "模块观察清单", "module"),
            ("risk_handling_sequence", "风险处理顺序", "action"),
        ):
            for item in plan.get(key) or []:
                add(module, str(item.get(field) or ""), str(item.get("priority") or ""), str(item.get("reason") or ""), "；".join(plan.get("recommended_actions") or []))
        return rows
