"""Read-only helpers for AI Dashboard scheduled export state."""

from __future__ import annotations

import json
from pathlib import Path


class AIDashboardExportScheduler:
    """Expose scheduled export config/history without running workers."""

    CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_dashboard_export_scheduler_config.json"
    HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_dashboard_export_scheduler_history.json"

    DEFAULT_CONFIG = {
        "enabled": False,
        "period": "day",
        "schedule_time": "09:00",
        "notify_channels": [],
        "email": {},
        "webhook": {},
        "summary": "当前未配置 AI Dashboard 调度导出。",
    }

    @staticmethod
    def _read_json(path: Path, fallback):
        if not path.exists():
            return fallback
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback
        return data

    @staticmethod
    def get_scheduler_config() -> dict:
        """Return scheduler config with stable defaults."""
        data = AIDashboardExportScheduler._read_json(
            AIDashboardExportScheduler.CONFIG_PATH,
            {},
        )
        if not isinstance(data, dict):
            data = {}
        config = dict(AIDashboardExportScheduler.DEFAULT_CONFIG)
        config.update(data)
        channels = config.get("notify_channels") or []
        if isinstance(channels, str):
            channels = [channels]
        config["notify_channels"] = [str(item).strip() for item in channels if str(item).strip()]
        return config

    @staticmethod
    def get_scheduler_history(limit: int = 7) -> list[dict]:
        """Return recent scheduler history records only."""
        data = AIDashboardExportScheduler._read_json(
            AIDashboardExportScheduler.HISTORY_PATH,
            [],
        )
        if not isinstance(data, list):
            return []
        history = [item for item in data if isinstance(item, dict)]
        try:
            safe_limit = max(1, int(limit or 7))
        except (TypeError, ValueError):
            safe_limit = 7
        return history[:safe_limit]

    @staticmethod
    def build_scheduler_summary(limit: int = 7) -> dict:
        """Build a read-only scheduler summary for dashboard display."""
        config = AIDashboardExportScheduler.get_scheduler_config()
        history = AIDashboardExportScheduler.get_scheduler_history(limit=limit)
        latest = history[0] if history else {}
        return {
            "config": config,
            "history": history,
            "latest": latest,
            "summary": config.get("summary") or "当前未配置 AI Dashboard 调度导出。",
        }
