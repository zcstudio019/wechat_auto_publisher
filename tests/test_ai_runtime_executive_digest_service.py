import unittest
from unittest.mock import patch

from services.ai_runtime_executive_digest_service import AIRuntimeExecutiveDigestService


class AIRuntimeExecutiveDigestServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_runtime_mission_control_center": {
                "mission_status": "active",
                "today_missions": [
                    {
                        "title": "复核 Forecast 风险",
                        "priority": "P1",
                        "source_module": "Forecast",
                        "summary": "趋势需观察",
                        "recommended_workspace": "runtime_workspace",
                        "recommended_route": "/ai-dashboard/mission-control",
                    }
                ],
                "critical_missions": [],
                "blocked_missions": [],
            },
            "ai_dashboard_ops_health_center": {"ops_status": "healthy", "summary": "ops ok"},
            "ai_runtime_forecast_center": {"forecast_status": "normal", "potential_risks": []},
            "ai_runtime_alert_center": {"alert_status": "normal", "warning_alerts": []},
            "ai_runtime_incident_center": {"incident_status": "none", "critical_incidents": []},
            "ai_dashboard_export_operations_center": {"operations_status": "normal"},
        }

    def test_build_executive_digest_returns_dict(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("digest_status", center)
        self.assertIn("digest_level", center)
        self.assertIn("one_line_summary", center)

    def test_one_line_summary_is_not_empty_and_short(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertTrue(center["one_line_summary"])
        self.assertLessEqual(len(center["one_line_summary"]), 80)

    def test_best_path_is_not_empty(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertTrue(center["best_path"])

    def test_recommended_workspace_is_not_empty(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertTrue(center["recommended_workspace"])

    def test_recommended_page_is_not_empty(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertTrue(center["recommended_page"])

    def test_must_watch_items_length_is_reasonable(self):
        center = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        self.assertLessEqual(len(center["must_watch_items"]), 5)
        self.assertLessEqual(len(center["blocked_items"]), 5)

    def test_critical_status_maps_to_l4(self):
        dashboard = self._dashboard_fixture()
        dashboard["ai_runtime_incident_center"]["incident_status"] = "critical"
        center = AIRuntimeExecutiveDigestService.build_executive_digest(dashboard)
        self.assertEqual(center["digest_status"], "critical")
        self.assertEqual(center["digest_level"], "L4")

    def test_markdown_export_contains_title(self):
        markdown = AIRuntimeExecutiveDigestService.build_executive_digest_markdown(
            AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        )
        self.assertIn("# AI Runtime 高层摘要中心", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/executive-digest", rules)
        self.assertIn("/ai-dashboard/executive-digest-export", rules)

        fixture = AIRuntimeExecutiveDigestService.build_executive_digest(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value=self._dashboard_fixture()):
            with patch("web_ui.app.AIRuntimeExecutiveDigestService.build_executive_digest", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/executive-digest")
                    txt_response = client.get("/ai-dashboard/executive-digest-export?format=txt")
                    csv_response = client.get("/ai-dashboard/executive-digest-export?format=csv")
                    md_response = client.get("/ai-dashboard/executive-digest-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Runtime 高层摘要中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)

    def test_dashboard_template_contains_executive_digest_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 高层摘要中心", template)
        self.assertIn("打开高层摘要", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("导出 Markdown", template)


if __name__ == "__main__":
    unittest.main()
