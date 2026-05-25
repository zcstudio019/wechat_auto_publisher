import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_dashboard_export_automation import AIDashboardExportAutomation


class AIDashboardExportAutomationTest(unittest.TestCase):
    def test_append_export_history_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            with patch.object(AIDashboardExportAutomation, "HISTORY_PATH", history_path):
                record = AIDashboardExportAutomation.append_export_history({
                    "status": "success",
                    "file_count": 1,
                    "success_files": ["ai_dashboard_all_reports.txt"],
                })
                summary = AIDashboardExportAutomation.build_export_history_summary(limit=5)

        self.assertEqual(record["status"], "success")
        self.assertEqual(summary["total_count"], 1)
        self.assertEqual(summary["latest"]["file_count"], 1)

    def test_corrupt_history_returns_empty_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            history_path.write_text("{bad json", encoding="utf-8")
            with patch.object(AIDashboardExportAutomation, "HISTORY_PATH", history_path):
                summary = AIDashboardExportAutomation.build_export_history_summary(limit=5)

        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(summary["latest"], {})

    def test_export_all_reports_rows_have_content(self):
        rows = AIDashboardExportAutomation.build_export_all_reports_rows({})
        self.assertTrue(rows)
        self.assertIsInstance(rows[0], dict)


if __name__ == "__main__":
    unittest.main()
