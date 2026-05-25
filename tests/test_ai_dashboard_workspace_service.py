import unittest
from unittest.mock import patch

from services.ai_dashboard_workspace_service import AIDashboardWorkspaceService


class AIDashboardWorkspaceServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_dashboard_admin_home_center": {
                "admin_home_status": "normal",
                "summary": "admin ok",
            },
            "ai_dashboard_navigation_center": {
                "navigation_status": "normal",
                "recommended_paths": [
                    {"name": "管理者路径", "steps": ["Admin Home", "Executive Dashboard"], "summary": "ok"}
                ],
            },
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
            "ai_dashboard_export_operations_center": {"operations_status": "normal"},
            "ai_dashboard_documentation_center": {"documentation_status": "normal"},
            "ai_runtime_forecast_center": {"forecast_status": "normal"},
            "ai_runtime_alert_center": {"alert_status": "normal"},
        }

    def test_build_workspace_center_returns_dict(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("workspace_status", center)
        self.assertIn("today_workspace", center)
        self.assertIn("quick_actions", center)
        self.assertIn("priority_work_items", center)
        self.assertIn("runtime_workbench", center)
        self.assertIn("ops_workbench", center)
        self.assertIn("export_workbench", center)
        self.assertIn("governance_workbench", center)
        self.assertIn("documentation_workbench", center)
        self.assertIn("admin_workbench", center)
        self.assertIn("pending_items", center)
        self.assertIn("blocked_items", center)
        self.assertIn("manager_workspace", center)
        self.assertIn("recommended_workspace", center)

    def test_manager_workspace_is_not_empty(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertTrue(center["manager_workspace"]["priority_modules"])

    def test_ops_workspace_is_not_empty(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertTrue(center["ops_workspace"]["priority_modules"])

    def test_runtime_workspace_is_not_empty(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertTrue(center["runtime_workspace"]["priority_modules"])

    def test_developer_workspace_is_not_empty(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertTrue(center["developer_workspace"]["priority_modules"])

    def test_recommended_workspace_is_not_empty(self):
        center = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_workspace"])
        self.assertIn("title", center["recommended_workspace"])

    def test_warning_ops_recommends_ops_workspace(self):
        dashboard = self._dashboard_fixture()
        dashboard["ai_dashboard_ops_health_center"]["ops_status"] = "warning"
        center = AIDashboardWorkspaceService.build_workspace_center(dashboard)
        self.assertEqual(center["recommended_workspace"]["title"], "运维工作台")

    def test_markdown_export_contains_title(self):
        markdown = AIDashboardWorkspaceService.build_workspace_markdown(
            AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        )
        self.assertIn("# AI Dashboard 工作台中心", markdown)
        self.assertIn("## 管理者工作台", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/workspace", rules)
        self.assertIn("/ai-dashboard/workspace-export", rules)

        fixture = AIDashboardWorkspaceService.build_workspace_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={}):
            with patch("web_ui.app.AIDashboardWorkspaceService.build_workspace_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/workspace")
                    txt_response = client.get("/ai-dashboard/workspace-export?format=txt")
                    csv_response = client.get("/ai-dashboard/workspace-export?format=csv")
                    md_response = client.get("/ai-dashboard/workspace-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 工作台中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
