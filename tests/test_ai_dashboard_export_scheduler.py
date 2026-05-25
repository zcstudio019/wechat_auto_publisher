import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_dashboard_export_scheduler import AIDashboardExportScheduler


class AIDashboardExportSchedulerTest(unittest.TestCase):
    def test_missing_config_and_history_return_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(AIDashboardExportScheduler, "CONFIG_PATH", root / "config.json"), \
                 patch.object(AIDashboardExportScheduler, "HISTORY_PATH", root / "history.json"):
                config = AIDashboardExportScheduler.get_scheduler_config()
                history = AIDashboardExportScheduler.get_scheduler_history()

        self.assertFalse(config["enabled"])
        self.assertEqual(config["period"], "day")
        self.assertEqual(history, [])

    def test_scheduler_config_and_history_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            history_path = root / "history.json"
            config_path.write_text(json.dumps({
                "enabled": True,
                "period": "week",
                "notify_channels": "email",
            }), encoding="utf-8")
            history_path.write_text(json.dumps([
                {"status": "success", "created_at": str(index)}
                for index in range(3)
            ]), encoding="utf-8")

            with patch.object(AIDashboardExportScheduler, "CONFIG_PATH", config_path), \
                 patch.object(AIDashboardExportScheduler, "HISTORY_PATH", history_path):
                config = AIDashboardExportScheduler.get_scheduler_config()
                history = AIDashboardExportScheduler.get_scheduler_history(limit=2)

        self.assertTrue(config["enabled"])
        self.assertEqual(config["period"], "week")
        self.assertEqual(config["notify_channels"], ["email"])
        self.assertEqual(len(history), 2)

    def test_scheduler_summary_contains_config_history_and_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history_path = root / "history.json"
            history_path.write_text(json.dumps([{"status": "failed"}]), encoding="utf-8")

            with patch.object(AIDashboardExportScheduler, "CONFIG_PATH", root / "config.json"), \
                 patch.object(AIDashboardExportScheduler, "HISTORY_PATH", history_path):
                summary = AIDashboardExportScheduler.build_scheduler_summary()

        self.assertIn("config", summary)
        self.assertEqual(summary["latest"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
