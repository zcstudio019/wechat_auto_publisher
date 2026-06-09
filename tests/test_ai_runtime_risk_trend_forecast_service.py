import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_risk_trend_forecast_service import AIRuntimeRiskTrendForecastService


class AIRuntimeRiskTrendForecastServiceTest(unittest.TestCase):
    def test_build_risk_trend_forecast_returns_dict(self):
        center = AIRuntimeRiskTrendForecastService.build_risk_trend_forecast({})
        self.assertIsInstance(center, dict)
        self.assertIn("forecast_status", center)

    def test_rising_and_declining_risks(self):
        center = AIRuntimeRiskTrendForecastService.build_risk_trend_forecast({
            "ai_runtime_signal_intelligence": {
                "critical_signals": [{"title": "critical signal storm"}],
                "warning_signals": [{"title": "warning"}],
            },
            "ai_runtime_event_timeline": {
                "warning_events": [{"title": "export recovered"}],
            },
        })
        self.assertIn(center["forecast_status"], {"critical", "warning"})
        self.assertTrue(center["rising_risks"])
        self.assertTrue(center["forecast_items"])

    def test_stable_status(self):
        center = AIRuntimeRiskTrendForecastService.build_risk_trend_forecast({})
        self.assertEqual(center["forecast_status"], "stable")

    def test_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeRiskTrendForecastService.build_risk_trend_forecast({})
        self.assertIn("/ai-dashboard/runtime-risk-trend-forecast-export", {rule.rule for rule in app.url_map.iter_rules()})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_risk_trend_forecast_center": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                self.assertEqual(client.get("/ai-dashboard/runtime-risk-trend-forecast-export?format=txt").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-risk-trend-forecast-export?format=csv").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-risk-trend-forecast-export?format=md").status_code, 200)

    def test_dashboard_page_contains_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 风险趋势预测中心", template)

    def test_no_automatic_logic_exists(self):
        source = Path("services/ai_runtime_risk_trend_forecast_service.py").read_text(encoding="utf-8")
        for forbidden in ["def execute", "def run", "def dispatch", "publish_approved_articles", "subprocess", "worker", "scheduler"]:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
