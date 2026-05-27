import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_strategy_engine import AIRuntimeStrategyEngine
from services.ai_runtime_strategy_service import AIRuntimeStrategyService


class AIRuntimeStrategySystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeStrategyEngine()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _simulation_center(self):
        return {
            "simulation_status": "critical",
            "worst_case_scenarios": [{"title": "release blocked", "risk_level": "critical"}],
            "risk_propagation_forecasts": [
                {"path": ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"], "risk_level": "critical"}
            ],
            "rollback_impacts": [{"target": "JSON", "rollback_plan": "restore json backup"}],
        }

    def _decision_center(self):
        return {
            "decision_status": "critical",
            "blocked_decisions": [{"title": "blocked", "priority": "critical"}],
            "high_risk_decisions": [{"title": "risk", "priority": "critical"}],
        }

    def _intervention_center(self):
        return {
            "root_cause_interventions": [
                {"target": "JSON_CORRUPTED", "priority": "critical"}
            ]
        }

    def _build_strategy(self):
        return self.engine.build_strategy(
            self._simulation_center(),
            self._decision_center(),
            self._intervention_center(),
            {"trust_status": "high"},
            {"confidence_status": "high"},
            {"mission_status": "active"},
        )

    def test_build_strategy_returns_dict(self):
        result = self.engine.build_strategy({}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("strategy_status", result)
        self.assertIn("short_term_strategies", result)

    def test_short_term_strategy_generated(self):
        result = self._build_strategy()
        titles = {item["title"] for item in result["short_term_strategies"]}
        self.assertIn("修复 JSON instability", titles)

    def test_mid_term_strategy_generated(self):
        result = self._build_strategy()
        titles = {item["title"] for item in result["mid_term_strategies"]}
        self.assertIn("Runtime Event 标准化", titles)

    def test_long_term_strategy_generated(self):
        result = self._build_strategy()
        titles = {item["title"] for item in result["long_term_strategies"]}
        self.assertIn("Runtime OS 分层稳定化", titles)

    def test_roadmap_generated(self):
        result = self._build_strategy()
        self.assertTrue(result["stability_roadmap"])
        self.assertTrue(result["automation_roadmap"])
        self.assertTrue(result["governance_roadmap"])

    def test_technical_debt_risk_generated(self):
        result = self._build_strategy()
        risks = {item["title"] for item in result["technical_debt_risks"]}
        self.assertIn("JSON coupling", risks)
        self.assertIn("Runtime high coupling", risks)

    def test_capability_priorities_generated(self):
        result = self._build_strategy()
        priorities = {item["capability"] for item in result["capability_priorities"]}
        self.assertIn("stability", priorities)
        self.assertIn("governance", priorities)

    def test_build_strategy_center_returns_dict(self):
        dashboard = {
            "ai_runtime_simulation_center": self._simulation_center(),
            "ai_runtime_decision_center": self._decision_center(),
            "ai_runtime_intervention_center": self._intervention_center(),
            "ai_runtime_trust_center": {"trust_status": "high"},
            "ai_runtime_confidence_center": {"confidence_status": "high"},
            "ai_runtime_task_command_center": {"mission_status": "active"},
        }
        center = AIRuntimeStrategyService.build_strategy_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["strategy_status"], "critical")
        self.assertTrue(center["technical_debt_risks"])

    def test_runtime_strategy_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-strategy-export", rules)

        for event_key in ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"]:
            self.bus.publish(event_key)
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-strategy-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-strategy-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-strategy-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 战略中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 战略中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_strategy_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 战略中心", template)


if __name__ == "__main__":
    unittest.main()
