import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_executive_operations_overview_service import AIRuntimeExecutiveOperationsOverviewService


class AIRuntimeExecutiveOperationsOverviewServiceTest(unittest.TestCase):
    def test_build_executive_operations_overview_returns_dict(self):
        center = AIRuntimeExecutiveOperationsOverviewService.build_executive_operations_overview({})
        self.assertIsInstance(center, dict)
        self.assertIn("overview_status", center)

    def test_status_detects_critical_and_attention(self):
        critical = AIRuntimeExecutiveOperationsOverviewService.build_executive_operations_overview({
            "ai_runtime_action_approval_center": {"approval_status": "blocked"}
        })
        self.assertEqual(critical["overview_status"], "critical")
        attention = AIRuntimeExecutiveOperationsOverviewService.build_executive_operations_overview({
            "ai_runtime_weekly_executive_report": {"report_status": "attention"}
        })
        self.assertEqual(attention["overview_status"], "attention")

    def test_critical_items_and_today_focus_exist(self):
        center = AIRuntimeExecutiveOperationsOverviewService.build_executive_operations_overview({
            "ai_runtime_one_page_console": {"today_must_do": [{"title": "Check ops"}]},
            "ai_runtime_monthly_board_report": {"strategic_threats": [{"title": "Release blocked"}]},
        })
        self.assertTrue(center["critical_items"])
        self.assertTrue(center["today_focus"])

    def test_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeExecutiveOperationsOverviewService.build_executive_operations_overview({})
        self.assertIn("/ai-dashboard/runtime-executive-operations-overview-export", {rule.rule for rule in app.url_map.iter_rules()})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_executive_operations_overview": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                self.assertEqual(client.get("/ai-dashboard/runtime-executive-operations-overview-export?format=txt").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-executive-operations-overview-export?format=csv").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-executive-operations-overview-export?format=md").status_code, 200)

    def test_dashboard_page_contains_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 执行运营总览", template)

    def test_no_automatic_logic_exists(self):
        source = Path("services/ai_runtime_executive_operations_overview_service.py").read_text(encoding="utf-8")
        for forbidden in ["def execute", "def run", "def dispatch", "publish_approved_articles", "subprocess", "worker", "scheduler"]:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
