import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_enhanced_executive_summary_service import AIRuntimeEnhancedExecutiveSummaryService


class AIRuntimeEnhancedExecutiveSummaryServiceTest(unittest.TestCase):
    def test_build_enhanced_executive_summary_returns_dict(self):
        center = AIRuntimeEnhancedExecutiveSummaryService.build_enhanced_executive_summary({})
        self.assertIsInstance(center, dict)
        self.assertIn("summary_status", center)

    def test_summary_status_and_sections(self):
        center = AIRuntimeEnhancedExecutiveSummaryService.build_enhanced_executive_summary({
            "ai_runtime_monthly_board_report": {"board_status": "critical", "strategic_threats": [{"title": "Governance risk"}]},
            "ai_runtime_execution_plan_center": {"plan_status": "attention", "high_risk_plans": [{"title": "High risk plan"}]},
            "ai_runtime_daily_operator_brief": {"must_do_today": [{"title": "Check approval"}]},
        })
        self.assertEqual(center["summary_status"], "critical")
        self.assertTrue(center["board_attention_items"])
        self.assertTrue(center["cto_attention_items"])
        self.assertTrue(center["operator_attention_items"])

    def test_headline_and_brief_are_not_empty(self):
        center = AIRuntimeEnhancedExecutiveSummaryService.build_enhanced_executive_summary({})
        self.assertTrue(center["headline"])
        self.assertTrue(center["executive_brief"])

    def test_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeEnhancedExecutiveSummaryService.build_enhanced_executive_summary({})
        self.assertIn("/ai-dashboard/runtime-enhanced-executive-summary-export", {rule.rule for rule in app.url_map.iter_rules()})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_enhanced_executive_summary": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                self.assertEqual(client.get("/ai-dashboard/runtime-enhanced-executive-summary-export?format=txt").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-enhanced-executive-summary-export?format=csv").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-enhanced-executive-summary-export?format=md").status_code, 200)

    def test_dashboard_page_contains_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 高管摘要增强中心", template)

    def test_no_automatic_logic_exists(self):
        source = Path("services/ai_runtime_enhanced_executive_summary_service.py").read_text(encoding="utf-8")
        for forbidden in ["def execute", "def run", "def dispatch", "publish_approved_articles", "subprocess", "worker", "scheduler"]:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
