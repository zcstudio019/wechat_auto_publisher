import unittest
from pathlib import Path
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

    def test_ai_dashboard_template_contains_quick_entry_matrix(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Dashboard 快捷入口", template)
        for title in [
            "管理首页",
            "工作台中心",
            "任务指挥中心",
            "高管仪表盘",
            "运维健康",
            "导出运营",
            "文档中心",
            "导航中心",
            "架构地图",
            "冒烟测试",
        ]:
            self.assertIn(title, template)
        self.assertIn("展开全部", template)
        self.assertIn("收起全部", template)

    def test_ai_dashboard_template_keeps_core_center_titles_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        for title in [
            "AI Dashboard 管理首页中心",
            "AI Dashboard 工作台中心",
            "AI Runtime 任务指挥中心",
            "AI Runtime Executive Dashboard Center",
            "AI Dashboard 运维健康中心",
            "AI Dashboard 导出运营中心",
            "AI Dashboard 文档中心",
            "AI Dashboard 导航与索引中心",
            "AI Dashboard 系统架构地图中心",
            "AI Dashboard 冒烟测试中心",
        ]:
            self.assertIn(title, template)

    def test_existing_dashboard_routes_and_exports_are_kept(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        for route in [
            "/ai-dashboard/smoke-test",
            "/ai-dashboard/ops-health",
            "/ai-dashboard/export-operations",
            "/ai-dashboard/documentation",
            "/ai-dashboard/navigation",
            "/ai-dashboard/architecture-map",
            "/ai-dashboard/home",
            "/ai-dashboard/workspace",
            "/ai-dashboard/mission-control",
        ]:
            self.assertIn(route, rules)
        for route in [
            "/ai-dashboard/home-export",
            "/ai-dashboard/workspace-export",
            "/ai-dashboard/mission-control-export",
            "/ai-dashboard/documentation-export",
            "/ai-dashboard/navigation-export",
            "/ai-dashboard/architecture-map-export",
            "/ai-dashboard/ops-health-export",
            "/ai-dashboard/export-all-reports",
        ]:
            self.assertIn(route, rules)


if __name__ == "__main__":
    unittest.main()
