import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService


def smoke(status="passed", checks=None):
    checks = checks or [
        {"name": "导出路由完整性", "status": "passed", "summary": "routes ok"},
        {"name": "模板标题完整性", "status": "passed", "summary": "titles ok"},
        {"name": "Runtime key 完整性", "status": "passed", "summary": "keys ok"},
    ]
    failed = [item for item in checks if item.get("status") == "failed"]
    warning = [item for item in checks if item.get("status") == "warning"]
    return {
        "status": status,
        "summary": f"smoke {status}",
        "checks": checks,
        "failed_checks": failed,
        "warning_checks": warning,
        "passed_checks": [item for item in checks if item.get("status") == "passed"],
    }


def export_ops(**overrides):
    payload = {
        "operations_status": "normal",
        "latest_export_result": {"status": "success"},
        "scheduler_history": [{"status": "success"}],
        "notification_status": {"email_enabled": True, "webhook_enabled": True},
        "failed_items": [],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class AIDashboardOpsHealthServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / "data"
        self.export_dir = self.root / "exports"
        self.data_dir.mkdir()
        self.export_dir.mkdir()
        self.patches = [
            patch.object(AIDashboardOpsHealthService, "DATA_DIR", self.data_dir),
            patch.object(AIDashboardOpsHealthService, "EXPORT_DIR", self.export_dir),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def _write_all_json(self):
        for filename in AIDashboardOpsHealthService.JSON_FILES:
            (self.data_dir / filename).write_text(json.dumps({"ok": True}), encoding="utf-8")

    def _build(self, smoke_payload=None, export_payload=None):
        with patch("services.ai_dashboard_ops_health_service.AIDashboardSmokeTestService.run_smoke_test", return_value=smoke_payload or smoke()), \
             patch("services.ai_dashboard_ops_health_service.AIDashboardExportOperationsService.build_export_operations_center", return_value=export_payload or export_ops()):
            return AIDashboardOpsHealthService.build_ops_health_center()

    def test_build_ops_health_center_returns_dict(self):
        center = self._build()
        self.assertIsInstance(center, dict)
        self.assertIn("health_status", center)
        self.assertIn("health_score", center)
        self.assertIn("runtime_status", center)
        self.assertIn("export_status", center)
        self.assertIn("scheduler_status", center)
        self.assertIn("json_file_status", center)
        self.assertIn("route_status", center)
        self.assertIn("template_status", center)
        self.assertIn("warning_items", center)
        self.assertIn("risk_items", center)
        self.assertIn("ops_status", center)
        self.assertIn("json_health", center)

    def test_smoke_test_fail_sets_critical(self):
        center = self._build(smoke_payload=smoke("failed", [
            {"name": "Dashboard 聚合执行", "status": "failed", "summary": "boom"}
        ]))
        self.assertEqual(center["ops_status"], "critical")
        self.assertEqual(center["health_status"], "critical")
        self.assertLess(center["health_score"], 100)

    def test_smoke_test_warning_sets_warning(self):
        center = self._build(smoke_payload=smoke("warning", [
            {"name": "关键 JSON 文件可读性", "status": "warning", "summary": "missing"}
        ]))
        self.assertEqual(center["ops_status"], "warning")
        self.assertEqual(center["health_status"], "warning")

    def test_json_broken_sets_warning(self):
        self._write_all_json()
        (self.data_dir / AIDashboardOpsHealthService.JSON_FILES[0]).write_text("{broken", encoding="utf-8")
        center = self._build()
        self.assertEqual(center["ops_status"], "warning")
        self.assertTrue(any(item["status"] == "broken" for item in center["json_health"]))
        self.assertGreaterEqual(center["json_file_status"]["broken_count"], 1)
        self.assertTrue(center["warning_items"])

    def test_export_storage_large_sets_warning_and_critical(self):
        (self.export_dir / "a.bin").write_bytes(b"123456")
        with patch.object(AIDashboardOpsHealthService, "STORAGE_WARNING_BYTES", 4), \
             patch.object(AIDashboardOpsHealthService, "STORAGE_CRITICAL_BYTES", 100):
            warning_center = self._build()
        with patch.object(AIDashboardOpsHealthService, "STORAGE_WARNING_BYTES", 4), \
             patch.object(AIDashboardOpsHealthService, "STORAGE_CRITICAL_BYTES", 5):
            critical_center = self._build()

        self.assertEqual(warning_center["export_storage"]["storage_status"], "warning")
        self.assertEqual(critical_center["export_storage"]["storage_status"], "critical")
        self.assertEqual(warning_center["ops_status"], "warning")

    def test_no_risk_sets_healthy(self):
        self._write_all_json()
        center = self._build()
        self.assertEqual(center["ops_status"], "healthy")
        self.assertEqual(center["health_status"], "healthy")
        self.assertEqual(center["health_score"], 100)
        self.assertEqual(center["ops_risks"], [])

    def test_route_template_runtime_key_health_extracts_checks(self):
        center = self._build(smoke_payload=smoke("passed", [
            {"name": "导出路由完整性", "status": "passed", "summary": "routes ok"},
            {"name": "模板标题完整性", "status": "passed", "summary": "titles ok"},
            {"name": "Runtime key 完整性", "status": "passed", "summary": "keys ok"},
        ]))
        self.assertEqual(center["route_health"][0]["status"], "passed")
        self.assertEqual(center["template_health"][0]["status"], "passed")
        self.assertEqual(center["runtime_key_health"][0]["status"], "passed")
        self.assertEqual(center["route_status"]["status"], "ok")
        self.assertEqual(center["template_status"]["status"], "ok")
        self.assertEqual(center["runtime_status"]["status"], "ok")

    def test_route_template_runtime_failures_set_warning(self):
        center = self._build(smoke_payload=smoke("passed", [
            {"name": "导出路由完整性", "status": "failed", "summary": "route missing"},
            {"name": "模板标题完整性", "status": "failed", "summary": "title missing"},
            {"name": "Runtime key 完整性", "status": "failed", "summary": "key missing"},
        ]))
        self.assertEqual(center["ops_status"], "warning")
        self.assertEqual(center["route_status"]["status"], "failed")
        self.assertEqual(center["template_status"]["status"], "failed")
        self.assertEqual(center["runtime_status"]["status"], "failed")
        self.assertTrue(center["ops_risks"])

    def test_empty_dashboard_fallback_shape(self):
        center = self._build(smoke_payload={}, export_payload={})
        self.assertIn(center["health_status"], {"healthy", "warning", "critical", "unknown"})
        self.assertIsInstance(center["warning_items"], list)
        self.assertIsInstance(center["recommended_actions"], list)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/ops-health", rules)
        self.assertIn("/ai-dashboard/ops-health-export", rules)

        fixture = {
            "health_status": "healthy",
            "health_score": 100,
            "ops_status": "healthy",
            "summary": "ok",
            "runtime_status": {"status": "ok", "summary": "ok"},
            "export_status": {"status": "ok", "failed_items": [], "warnings": []},
            "scheduler_status": {"status": "ok", "summary": "ok"},
            "json_file_status": {"status": "ok", "broken_count": 0, "missing_count": 0},
            "route_status": {"status": "ok", "summary": "ok"},
            "template_status": {"status": "ok", "summary": "ok"},
            "smoke_test_status": {"status": "passed", "failed_count": 0, "warning_count": 0},
            "export_operations_status": {"operations_status": "normal", "failed_items": [], "warnings": []},
            "json_health": [],
            "export_storage": {"file_count": 0, "total_size": "0 B", "storage_status": "ok"},
            "route_health": [],
            "template_health": [],
            "runtime_key_health": [],
            "warning_items": [],
            "risk_items": [],
            "ops_risks": [],
            "recommended_actions": ["定期运行冒烟测试"],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardOpsHealthService.build_ops_health_center", return_value=fixture):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/ops-health")
                txt_response = client.get("/ai-dashboard/ops-health-export?format=txt")
                csv_response = client.get("/ai-dashboard/ops-health-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 运维健康中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
