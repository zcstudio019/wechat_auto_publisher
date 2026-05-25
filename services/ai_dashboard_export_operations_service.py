"""AI Dashboard 导出运营中心只读服务。

该模块只读取导出、调度和通知状态，不执行导出、不启动调度、
不发送邮件或 webhook，也不修改任何业务状态。
"""

from __future__ import annotations

from pathlib import Path

from services.ai_dashboard_export_automation import AIDashboardExportAutomation
from services.ai_dashboard_export_scheduler import AIDashboardExportScheduler


class AIDashboardExportOperationsService:
    """构建 AI Dashboard 导出运营中心的只读视图。"""

    EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "ai_dashboard_exports"

    @staticmethod
    def build_export_operations_center() -> dict:
        export_history = AIDashboardExportAutomation.build_export_history_summary(limit=10)
        latest_export = dict(export_history.get("latest") or {})
        scheduler_config = AIDashboardExportScheduler.get_scheduler_config()
        scheduler_history = AIDashboardExportScheduler.get_scheduler_history(limit=7)
        recent_files = AIDashboardExportOperationsService._scan_recent_export_files(limit=20)
        notification_status = AIDashboardExportOperationsService._build_notification_status(
            scheduler_config,
            scheduler_history,
        )

        warnings = AIDashboardExportOperationsService._build_warnings(
            latest_export,
            scheduler_config,
            scheduler_history,
            notification_status,
        )
        failed_items = AIDashboardExportOperationsService._build_failed_items(
            latest_export,
            scheduler_history,
        )
        operations_status = AIDashboardExportOperationsService._resolve_operations_status(
            latest_export,
            scheduler_history,
            warnings,
            failed_items,
        )
        recommended_actions = AIDashboardExportOperationsService._build_recommended_actions(
            latest_export,
            recent_files,
            notification_status,
            failed_items,
        )

        summary = AIDashboardExportOperationsService._build_summary(
            operations_status,
            latest_export,
            scheduler_config,
            warnings,
        )
        return {
            "operation_status": operations_status,
            "operations_status": operations_status,
            "manual_export_entry": {
                "export_all_reports_url": "/ai-dashboard/export-all-reports?format=txt",
                "default_period": "day",
                "default_mode": "manual",
                "summary": "手动批量导出 AI Dashboard 全部报表，触发现有只读导出接口。",
            },
            "scheduled_export_entry": {
                "schedule_submit_url": "/ai-dashboard/export-all-reports?format=txt&period=day",
                "supported_periods": ["day", "week", "month"],
                "supported_notify_channels": ["email", "webhook"],
                "summary": "集中查看调度日报导出配置和最近执行结果，不新增调度动作。",
            },
            "latest_export_result": latest_export,
            "latest_export_files": recent_files[:10],
            "recent_export_files": recent_files,
            "schedule_config": scheduler_config,
            "scheduler_config": scheduler_config,
            "schedule_history": scheduler_history,
            "scheduler_history": scheduler_history,
            "notification_status": notification_status,
            "warnings": warnings,
            "failed_items": failed_items,
            "recommended_actions": recommended_actions,
            "summary": summary,
        }

    @staticmethod
    def _scan_recent_export_files(limit: int = 20) -> list[dict]:
        export_dir = AIDashboardExportOperationsService.EXPORT_DIR
        if not export_dir.exists() or not export_dir.is_dir():
            return []

        files = []
        for path in export_dir.iterdir():
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append({
                "filename": path.name,
                "path": str(path),
                "size": AIDashboardExportOperationsService._format_size(stat.st_size),
                "created_at": AIDashboardExportOperationsService._format_timestamp(stat.st_ctime),
                "download_url": "",
                "_sort_time": stat.st_ctime,
            })

        files.sort(key=lambda item: item.get("_sort_time") or 0, reverse=True)
        safe_limit = max(1, int(limit or 20))
        return [
            {key: value for key, value in item.items() if key != "_sort_time"}
            for item in files[:safe_limit]
        ]

    @staticmethod
    def _format_size(size: int) -> str:
        size = max(0, int(size or 0))
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        from datetime import datetime

        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

    @staticmethod
    def _build_notification_status(config: dict, scheduler_history: list[dict]) -> dict:
        channels = set(config.get("notify_channels") or [])
        email_config = config.get("email") or {}
        webhook_config = config.get("webhook") or {}
        email_enabled = bool("email" in channels or email_config.get("enabled") or email_config.get("smtp_host"))
        webhook_enabled = bool("webhook" in channels or webhook_config.get("enabled") or webhook_config.get("url"))

        last_email_status = ""
        last_webhook_status = ""
        for item in scheduler_history or []:
            if not last_email_status and item.get("email_status"):
                last_email_status = str(item.get("email_status"))
            if not last_webhook_status and item.get("webhook_status"):
                last_webhook_status = str(item.get("webhook_status"))
            notification = item.get("notification_status") or {}
            if isinstance(notification, dict):
                if not last_email_status and notification.get("email_status"):
                    last_email_status = str(notification.get("email_status"))
                if not last_webhook_status and notification.get("webhook_status"):
                    last_webhook_status = str(notification.get("webhook_status"))

        return {
            "email_enabled": email_enabled,
            "webhook_enabled": webhook_enabled,
            "last_email_status": last_email_status or "not_configured",
            "last_webhook_status": last_webhook_status or "not_configured",
        }

    @staticmethod
    def _build_warnings(latest_export: dict, config: dict, history: list[dict], notifications: dict) -> list[str]:
        warnings = []
        if not latest_export:
            warnings.append("最近无导出历史。")
        if not history:
            warnings.append("最近无调度导出历史。")
        if not notifications.get("email_enabled"):
            warnings.append("SMTP 邮件通知未配置。")
        if not notifications.get("webhook_enabled"):
            warnings.append("Webhook 通知未配置。")
        if not config.get("enabled"):
            warnings.append("调度导出当前未启用。")
        return warnings

    @staticmethod
    def _build_failed_items(latest_export: dict, history: list[dict]) -> list[str]:
        failed_items = []
        for file_name in latest_export.get("failed_files") or []:
            failed_items.append(f"批量导出失败文件：{file_name}")
        if latest_export.get("status") == "failed" and latest_export.get("message"):
            failed_items.append(f"最近批量导出失败：{latest_export.get('message')}")

        latest_schedule = (history or [{}])[0] if history else {}
        if latest_schedule.get("status") == "failed":
            failed_items.append(
                f"最近调度导出失败：{latest_schedule.get('message') or latest_schedule.get('created_at') or 'unknown'}"
            )
        return failed_items

    @staticmethod
    def _resolve_operations_status(
        latest_export: dict,
        history: list[dict],
        warnings: list[str],
        failed_items: list[str],
    ) -> str:
        latest_schedule = (history or [{}])[0] if history else {}
        if latest_export.get("failed_files") or latest_export.get("status") == "failed" or latest_schedule.get("status") == "failed":
            return "failed"
        if failed_items:
            return "failed"
        if warnings or not latest_export:
            return "warning"
        return "normal"

    @staticmethod
    def _build_summary(
        operations_status: str,
        latest_export: dict,
        config: dict,
        warnings: list[str],
    ) -> str:
        if not latest_export and not config.get("enabled"):
            return "当前暂无 Dashboard 导出运营数据。"
        if operations_status == "failed":
            return "存在失败导出，请检查错误信息。"
        if operations_status == "warning":
            return warnings[0] if warnings else "导出运营需要关注。"
        return "导出运营状态正常。"

    @staticmethod
    def _build_recommended_actions(
        latest_export: dict,
        recent_files: list[dict],
        notifications: dict,
        failed_items: list[str],
    ) -> list[str]:
        actions = []
        if not notifications.get("email_enabled"):
            actions.append("配置 SMTP 邮件通知")
        if not notifications.get("webhook_enabled"):
            actions.append("配置 Webhook 通知")
        actions.append("定期清理旧导出文件")
        if failed_items:
            actions.append("检查失败导出项")
        if latest_export.get("zip_path") or any((item.get("filename") or "").lower().endswith(".zip") for item in recent_files):
            actions.append("下载最新 ZIP 归档")
        actions.append("每周复盘导出报告")
        return actions[:8]
