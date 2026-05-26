import unittest
from unittest.mock import patch

from services.ai_runtime_executive_summary_service import AIRuntimeExecutiveSummaryService


class AIRuntimeExecutiveSummaryServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "summary": {"total_articles": 8, "high_risk_articles": 1, "avg_health_score": 82},
            "ai_dashboard_workspace_center": {"workspace_status": "normal", "summary": "workspace ok"},
            "ai_runtime_task_command_center": {"task_command_status": "normal", "summary": "task ok"},
            "ai_dashboard_action_launchpad_center": {"launchpad_status": "normal", "summary": "launchpad ok"},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy", "summary": "ops ok"},
            "ai_dashboard_export_operations_center": {"operations_status": "normal", "summary": "export ok"},
            "ai_autoops_control_tower": {"control_status": "normal", "summary": "autoops ok"},
            "ai_runtime_trust_center": {"trust_status": "high", "summary": "trust ok"},
            "ai_runtime_confidence_center": {"confidence_status": "high", "summary": "confidence ok"},
        }

    def test_build_runtime_executive_summary_center_returns_required_fields(self):
        center = AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_center(self._dashboard_fixture())
        for key in [
            "executive_summary_status",
            "summary",
            "top_level_conclusion",
            "health_snapshot",
            "risk_snapshot",
            "runtime_snapshot",
            "ops_snapshot",
            "export_snapshot",
            "automation_snapshot",
            "today_key_points",
            "critical_risks",
            "executive_recommendations",
            "decision_needed",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_export_helpers_return_data(self):
        center = AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_center(self._dashboard_fixture())
        self.assertIn("AI Runtime \u9ad8\u5c42\u6458\u8981\u4e2d\u5fc3", AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_text(center))
        self.assertTrue(AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_rows(center))

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-executive-summary", rules)
        self.assertIn("/ai-dashboard/runtime-executive-summary-export", rules)

        fixture = AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value=self._dashboard_fixture()):
            with patch("web_ui.app.AIRuntimeExecutiveSummaryService.build_runtime_executive_summary_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/runtime-executive-summary")
                    txt_response = client.get("/ai-dashboard/runtime-executive-summary-export?format=txt")
                    csv_response = client.get("/ai-dashboard/runtime-executive-summary-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Runtime \u9ad8\u5c42\u6458\u8981\u4e2d\u5fc3".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)

    def test_dashboard_template_contains_executive_summary_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime \u9ad8\u5c42\u6458\u8981\u4e2d\u5fc3", template)
        self.assertIn("ai_runtime_executive_summary_center", template)
        self.assertIn("\u67e5\u770b\u9ad8\u5c42\u6458\u8981\u8be6\u60c5", template)


if __name__ == "__main__":
    unittest.main()
