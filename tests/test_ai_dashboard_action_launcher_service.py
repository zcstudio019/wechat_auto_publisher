import unittest
from unittest.mock import patch

from services.ai_dashboard_action_launcher_service import AIDashboardActionLauncherService


class AIDashboardActionLauncherServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
            "ai_runtime_forecast_center": {"forecast_status": "normal"},
            "ai_runtime_incident_center": {"incident_status": "none"},
            "ai_runtime_alert_center": {"alert_status": "normal"},
        }

    def test_build_action_launcher_center_returns_dict(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("launcher_status", center)
        self.assertIn("page_launchers", center)
        self.assertIn("workspace_launchers", center)
        self.assertIn("runtime_launchers", center)
        self.assertIn("ops_launchers", center)
        self.assertIn("recommended_shortcuts", center)

    def test_build_action_launchpad_center_returns_required_fields(self):
        center = AIDashboardActionLauncherService.build_action_launchpad_center(self._dashboard_fixture())
        for key in [
            "launchpad_status",
            "summary",
            "action_groups",
            "quick_launch_actions",
            "manual_confirm_actions",
            "safe_readonly_actions",
            "risky_actions",
            "blocked_actions",
            "approval_required_actions",
            "runtime_linked_actions",
            "export_actions",
            "ops_actions",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_page_launchers_not_empty(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertTrue(center["page_launchers"])

    def test_workspace_launchers_not_empty(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertTrue(center["workspace_launchers"])

    def test_runtime_launchers_not_empty(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertTrue(center["runtime_launchers"])

    def test_ops_launchers_not_empty(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertTrue(center["ops_launchers"])

    def test_recommended_shortcuts_not_empty(self):
        center = AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_shortcuts"])

    def test_busy_status_from_runtime_warning(self):
        dashboard = self._dashboard_fixture()
        dashboard["ai_runtime_forecast_center"]["forecast_status"] = "warning"
        center = AIDashboardActionLauncherService.build_action_launcher_center(dashboard)
        self.assertEqual(center["launcher_status"], "busy")

    def test_markdown_export_contains_title(self):
        markdown = AIDashboardActionLauncherService.build_action_launcher_markdown(
            AIDashboardActionLauncherService.build_action_launcher_center(self._dashboard_fixture())
        )
        self.assertIn("# AI Dashboard 动作启动台中心", markdown)
        self.assertIn("## 页面动作入口", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/action-launchpad", rules)
        self.assertIn("/ai-dashboard/action-launchpad-export", rules)
        self.assertIn("/ai-dashboard/action-launcher", rules)
        self.assertIn("/ai-dashboard/action-launcher-export", rules)

        fixture = AIDashboardActionLauncherService.build_action_launchpad_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value=self._dashboard_fixture()):
            with patch("web_ui.app.AIDashboardActionLaunchpadService.build_action_launchpad_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/action-launchpad")
                    txt_response = client.get("/ai-dashboard/action-launchpad-export?format=txt")
                    csv_response = client.get("/ai-dashboard/action-launchpad-export?format=csv")
                    md_response = client.get("/ai-dashboard/action-launchpad-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 动作启动台中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)

    def test_dashboard_template_contains_action_launcher_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 动作启动台中心", template)
        self.assertIn("查看动作启动台详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("ai_dashboard_action_launchpad_center", template)


if __name__ == "__main__":
    unittest.main()
