import unittest
from unittest.mock import patch

from services.ai_runtime_mission_control_service import AIRuntimeMissionControlService


class AIRuntimeMissionControlServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_dashboard_workspace_center": {
                "recommended_workspace": {
                    "title": "管理者工作台",
                    "summary": "workspace ok",
                    "reason": "normal",
                }
            },
            "ai_runtime_forecast_center": {
                "forecast_status": "normal",
                "potential_risks": [{"title": "关注趋势波动", "summary": "观察 Runtime 趋势", "priority": "medium"}],
                "future_trends": [{"title": "健康趋势观察", "summary": "继续观察"}],
            },
            "ai_runtime_predictive_action_center": {
                "priority_actions": [{"title": "复核预测动作", "summary": "只读复核", "priority": "high"}],
                "potential_blockers": [{"title": "潜在阻塞", "summary": "blocked runtime path", "priority": "critical"}],
            },
            "ai_runtime_continuous_improvement_center": {
                "recommended_actions": ["沉淀改进建议"],
            },
            "ai_dashboard_ops_maintenance_center": {
                "today_tasks": [{"task": "检查运维健康", "reason": "daily check", "priority": "medium"}],
            },
            "ai_dashboard_export_operations_center": {
                "operations_status": "normal",
                "warnings": ["检查导出归档"],
            },
            "ai_runtime_alert_center": {
                "alert_status": "normal",
                "warning_alerts": [{"title": "运行时提醒", "summary": "warning alert"}],
            },
            "ai_runtime_incident_center": {"incident_status": "none", "critical_incidents": []},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
        }

    def test_build_mission_control_center_returns_dict(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("task_command_status", center)
        self.assertIn("today_command", center)
        self.assertIn("task_groups", center)
        self.assertIn("priority_tasks", center)
        self.assertIn("manual_confirm_tasks", center)
        self.assertIn("blocked_tasks", center)
        self.assertIn("runtime_dependencies", center)
        self.assertIn("execution_order", center)
        self.assertIn("risk_tasks", center)
        self.assertIn("mission_status", center)
        self.assertIn("today_missions", center)

    def test_today_missions_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["today_missions"])

    def test_critical_missions_returns_list(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertIsInstance(center["critical_missions"], list)

    def test_recommended_execution_order_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_execution_order"])

    def test_recommended_workspaces_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_workspaces"])

    def test_recommended_exports_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_exports"])

    def test_critical_status_from_incident(self):
        dashboard = self._dashboard_fixture()
        dashboard["ai_runtime_incident_center"]["incident_status"] = "critical"
        center = AIRuntimeMissionControlService.build_mission_control_center(dashboard)
        self.assertEqual(center["mission_status"], "critical")

    def test_markdown_export_contains_title(self):
        markdown = AIRuntimeMissionControlService.build_mission_control_markdown(
            AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        )
        self.assertIn("# AI Runtime 任务指挥中心", markdown)
        self.assertIn("## 今日任务", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-task-command", rules)
        self.assertIn("/ai-dashboard/runtime-task-command-export", rules)
        self.assertIn("/ai-dashboard/mission-control", rules)
        self.assertIn("/ai-dashboard/mission-control-export", rules)

        fixture = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={}):
            with patch("web_ui.app.AIRuntimeMissionControlService.build_mission_control_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/runtime-task-command")
                    txt_response = client.get("/ai-dashboard/runtime-task-command-export?format=txt")
                    csv_response = client.get("/ai-dashboard/runtime-task-command-export?format=csv")
                    md_response = client.get("/ai-dashboard/runtime-task-command-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Runtime 任务指挥中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
