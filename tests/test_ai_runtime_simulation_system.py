import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_simulation_engine import AIRuntimeSimulationEngine
from services.ai_runtime_simulation_service import AIRuntimeSimulationService


class AIRuntimeSimulationSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeSimulationEngine()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _decisions(self):
        return [
            {
                "title": "Decide root cause response: JSON_CORRUPTED",
                "decision_type": "intervention",
                "priority": "critical",
                "decision_status": "manual_only",
                "confidence": "high",
                "trust_level": "high",
                "risk": "Root-cause response may affect downstream Runtime centers.",
                "rollback_plan": "Restore JSON backup and re-check Runtime state before changing configuration.",
            },
            {
                "title": "Continue read-only Runtime observation",
                "decision_type": "observation",
                "priority": "medium",
                "decision_status": "recommended",
                "confidence": "high",
                "trust_level": "high",
                "risk": "Low execution risk because no action is performed.",
                "rollback_plan": "Stop recommendation display and return to previous dashboard snapshot.",
            },
        ]

    def _causal_graph(self):
        return {
            "root_causes": [
                {"node_id": "JSON_CORRUPTED", "severity": "critical", "confidence": "high"}
            ],
            "critical_paths": [
                {
                    "path": ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"],
                    "severity": "critical",
                    "confidence": "high",
                }
            ],
        }

    def _intervention_center(self):
        return {
            "root_cause_interventions": [
                {
                    "title": "人工检查 JSON 写入来源",
                    "target": "JSON_CORRUPTED",
                    "intervention_type": "json",
                    "priority": "critical",
                    "expected_effect": "降低 Runtime 读取异常继续传播的概率。",
                }
            ],
            "blocking_interventions": [
                {
                    "title": "人工阻断风险传播链",
                    "target": "JSON_CORRUPTED -> SMOKE_TEST_FAILED -> OPS_CRITICAL -> RELEASE_BLOCKED",
                    "priority": "critical",
                    "reason": "关键因果链存在传播风险。",
                }
            ],
        }

    def _signal_center(self):
        return {
            "signal_status": "critical",
            "critical_signals": [{"signal_key": "CRITICAL_CLUSTER"}],
        }

    def test_simulate_returns_dict(self):
        result = self.engine.simulate([], {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("simulations", result)
        self.assertIn("recommended_actions", result)

    def test_simulation_generated(self):
        result = self.engine.simulate(self._decisions(), {}, {}, {})
        self.assertTrue(result["simulations"])
        self.assertEqual(result["simulations"][0]["simulation_type"], "intervention")

    def test_best_case_generated(self):
        result = self.engine.simulate(self._decisions(), {}, {}, self._signal_center())
        self.assertTrue(result["best_case_scenarios"])

    def test_worst_case_generated(self):
        result = self.engine.simulate(
            self._decisions(),
            self._causal_graph(),
            self._intervention_center(),
            self._signal_center(),
        )
        self.assertTrue(result["worst_case_scenarios"])

    def test_propagation_forecast_generated(self):
        result = self.engine.simulate(self._decisions(), self._causal_graph(), {}, {})
        self.assertTrue(result["risk_propagation_forecasts"])
        paths = [item["path"] for item in result["risk_propagation_forecasts"]]
        self.assertIn(["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"], paths)

    def test_rollback_impact_generated(self):
        result = self.engine.simulate(self._decisions(), {}, {}, {})
        self.assertTrue(result["rollback_impacts"])
        self.assertIn("JSON", result["rollback_impacts"][0]["rollback_plan"])

    def test_build_simulation_center_returns_dict(self):
        dashboard = {
            "ai_runtime_decision_center": {"decisions": self._decisions()},
            "ai_runtime_causal_graph_center": self._causal_graph(),
            "ai_runtime_intervention_center": self._intervention_center(),
            "ai_runtime_signal_intelligence": self._signal_center(),
        }
        center = AIRuntimeSimulationService.build_simulation_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn("simulation_status", center)
        self.assertTrue(center["simulations"])

    def test_critical_status_correct(self):
        dashboard = {
            "ai_runtime_decision_center": {"decisions": self._decisions()},
            "ai_runtime_causal_graph_center": self._causal_graph(),
            "ai_runtime_intervention_center": self._intervention_center(),
            "ai_runtime_signal_intelligence": self._signal_center(),
        }
        center = AIRuntimeSimulationService.build_simulation_center(dashboard)
        self.assertEqual(center["simulation_status"], "critical")

    def test_runtime_simulation_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-simulation-export", rules)

        for event_key in ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"]:
            self.bus.publish(event_key)
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-simulation-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-simulation-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-simulation-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 模拟推演中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 模拟推演中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_simulation_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 模拟推演中心", template)


if __name__ == "__main__":
    unittest.main()
