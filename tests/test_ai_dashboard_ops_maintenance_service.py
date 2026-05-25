import unittest
from unittest.mock import patch

from services.ai_dashboard_ops_maintenance_service import AIDashboardOpsMaintenanceService


def health_fixture(**overrides):
    payload = {
        "ops_status": "healthy",
        "health_status": "healthy",
        "smoke_test_status": {"status": "passed", "summary": "ok", "failed_count": 0, "warning_count": 0},
        "export_operations_status": {
            "operations_status": "normal",
            "scheduler_history": [{"status": "success"}],
            "notification_status": {"email_enabled": True, "webhook_enabled": True},
            "failed_items": [],
            "warnings": [],
        },
        "json_health": [{"file": "ai_runtime_alerts.json", "status": "ok", "summary": "ok"}],
        "export_storage": {"file_count": 0, "total_size": "0 B", "storage_status": "ok"},
        "route_health": [{"name": "导出路由完整性", "status": "passed", "summary": "ok"}],
        "template_health": [{"name": "模板标题完整性", "status": "passed", "summary": "ok"}],
        "runtime_key_health": [{"name": "Runtime key 完整性", "status": "passed", "summary": "ok"}],
        "ops_risks": [],
        "recommended_actions": [],
    }
    payload.update(overrides)
    return payload


class AIDashboardOpsMaintenanceServiceTest(unittest.TestCase):
    def _build(self, health):
        with patch("services.ai_dashboard_ops_maintenance_service.AIDashboardOpsHealthService.build_ops_health_center", return_value=health):
            return AIDashboardOpsMaintenanceService.build_maintenance_plan()

    def test_build_maintenance_plan_returns_dict(self):
        plan = self._build(health_fixture())
        self.assertIsInstance(plan, dict)
        self.assertIn("maintenance_status", plan)
        self.assertIn("today_tasks", plan)
        self.assertIn("archive_suggestions", plan)
        self.assertIn("test_priorities", plan)

    def test_ops_health_critical_sets_critical(self):
        plan = self._build(health_fixture(ops_status="critical"))
        self.assertEqual(plan["maintenance_status"], "critical")

    def test_ops_health_warning_sets_attention(self):
        plan = self._build(health_fixture(ops_status="warning"))
        self.assertEqual(plan["maintenance_status"], "attention")

    def test_no_risk_sets_normal(self):
        plan = self._build(health_fixture())
        self.assertEqual(plan["maintenance_status"], "normal")

    def test_today_tasks_are_built_from_failures(self):
        plan = self._build(health_fixture(
            smoke_test_status={"status": "failed", "summary": "smoke failed"},
            export_operations_status={
                "scheduler_history": [{"status": "failed", "message": "schedule failed"}],
                "notification_status": {"email_enabled": False, "webhook_enabled": False},
                "failed_items": [],
                "warnings": [],
            },
            json_health=[{"file": "bad.json", "status": "broken", "summary": "broken"}],
            export_storage={"file_count": 600, "total_size": "600 MB", "storage_status": "warning"},
        ))
        tasks = [item["task"] for item in plan["today_tasks"]]
        self.assertIn("检查 Smoke Test 失败项", tasks)
        self.assertIn("检查导出调度失败", tasks)
        self.assertIn("检查损坏 JSON", tasks)
        self.assertIn("检查导出文件过大", tasks)
        self.assertIn("检查通知配置", tasks)

    def test_weekly_tasks_cleanup_json_and_test_priority_are_present(self):
        plan = self._build(health_fixture())
        self.assertTrue(any(item["task"] == "运行全量测试" for item in plan["weekly_tasks"]))
        self.assertTrue(any(item["suggestion"] == "清理旧导出文件" for item in plan["cleanup_suggestions"]))
        self.assertTrue(any(item["suggestion"] == "备份损坏 JSON" for item in plan["json_repair_suggestions"]))
        self.assertTrue(any(item["suggestion"] == "每日导出归档" for item in plan["archive_suggestions"]))
        self.assertTrue(any(item["test"] == "smoke test" for item in plan["test_priorities"]))

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/ops-maintenance", rules)
        self.assertIn("/ai-dashboard/ops-maintenance-export", rules)

        fixture = {
            "maintenance_status": "normal",
            "summary": "ok",
            "today_tasks": [{"task": "完成 Dashboard 只读巡检", "priority": "normal", "reason": "ok"}],
            "weekly_tasks": [],
            "cleanup_suggestions": [],
            "json_repair_suggestions": [],
            "archive_suggestions": [],
            "test_priorities": [],
            "module_watchlist": [],
            "risk_handling_sequence": [],
            "recommended_actions": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardOpsMaintenanceService.build_maintenance_plan", return_value=fixture):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/ops-maintenance")
                txt_response = client.get("/ai-dashboard/ops-maintenance-export?format=txt")
                csv_response = client.get("/ai-dashboard/ops-maintenance-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 运维维护计划中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
