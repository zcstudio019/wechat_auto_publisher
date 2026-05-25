import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_dashboard_export_automation import AIDashboardExportAutomation
from services.ai_dashboard_export_operations_service import AIDashboardExportOperationsService
from services.ai_dashboard_export_scheduler import AIDashboardExportScheduler


class AIDashboardExportOperationsServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history_path = self.root / "ai_dashboard_export_history.json"
        self.scheduler_config_path = self.root / "scheduler_config.json"
        self.scheduler_history_path = self.root / "scheduler_history.json"
        self.export_dir = self.root / "exports"
        self.export_dir.mkdir()

        self.patches = [
            patch.object(AIDashboardExportAutomation, "HISTORY_PATH", self.history_path),
            patch.object(AIDashboardExportScheduler, "CONFIG_PATH", self.scheduler_config_path),
            patch.object(AIDashboardExportScheduler, "HISTORY_PATH", self.scheduler_history_path),
            patch.object(AIDashboardExportOperationsService, "EXPORT_DIR", self.export_dir),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def _write_json(self, path, data):
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_build_export_operations_center_returns_dict(self):
        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertIsInstance(center, dict)
        self.assertIn("operations_status", center)
        self.assertIn("manual_export_entry", center)

    def test_no_export_history_falls_back_to_warning(self):
        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertEqual(center["operations_status"], "warning")
        self.assertTrue(center["warnings"])

    def test_success_export_history_can_be_normal(self):
        self._write_json(self.history_path, [{
            "status": "success",
            "file_count": 1,
            "failed_files": [],
            "created_at": "2026-05-25 09:00:00",
        }])
        self._write_json(self.scheduler_config_path, {
            "enabled": True,
            "notify_channels": ["email", "webhook"],
            "email": {"smtp_host": "smtp.example.com"},
            "webhook": {"url": "https://example.com/hook"},
        })
        self._write_json(self.scheduler_history_path, [{
            "status": "success",
            "email_status": "success",
            "webhook_status": "success",
            "created_at": "2026-05-25 09:01:00",
        }])

        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertEqual(center["operations_status"], "normal")
        self.assertEqual(center["failed_items"], [])

    def test_failed_export_history_is_failed(self):
        self._write_json(self.history_path, [{
            "status": "failed",
            "file_count": 0,
            "failed_files": ["bad.csv"],
            "message": "export failed",
        }])

        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertEqual(center["operations_status"], "failed")
        self.assertTrue(center["failed_items"])

    def test_recent_export_files_scans_files(self):
        (self.export_dir / "report.txt").write_text("ok", encoding="utf-8")
        (self.export_dir / "archive.zip").write_bytes(b"zip")

        center = AIDashboardExportOperationsService.build_export_operations_center()
        names = {item["filename"] for item in center["recent_export_files"]}
        self.assertIn("report.txt", names)
        self.assertIn("archive.zip", names)
        self.assertTrue(all("download_url" in item for item in center["recent_export_files"]))

    def test_notification_status_is_built_from_config_and_history(self):
        self._write_json(self.scheduler_config_path, {
            "notify_channels": ["email", "webhook"],
            "email": {"smtp_host": "smtp.example.com"},
            "webhook": {"url": "https://example.com/hook"},
        })
        self._write_json(self.scheduler_history_path, [{
            "status": "success",
            "email_status": "sent",
            "webhook_status": "sent",
        }])

        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertTrue(center["notification_status"]["email_enabled"])
        self.assertTrue(center["notification_status"]["webhook_enabled"])
        self.assertEqual(center["notification_status"]["last_email_status"], "sent")

    def test_scheduler_history_is_limited_to_seven(self):
        self._write_json(self.scheduler_history_path, [
            {"status": "success", "created_at": str(index)}
            for index in range(10)
        ])

        center = AIDashboardExportOperationsService.build_export_operations_center()
        self.assertEqual(len(center["scheduler_history"]), 7)

    def test_route_and_page_title_exist(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/export-operations", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            response = client.get("/ai-dashboard/export-operations")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 导出运营中心".encode("utf-8"), response.data)


if __name__ == "__main__":
    unittest.main()
