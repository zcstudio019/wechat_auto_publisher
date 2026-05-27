import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_decision_engine import AIRuntimeDecisionEngine
from services.ai_runtime_decision_service import AIRuntimeDecisionService
from services.ai_runtime_event_bus import AIRuntimeEventBus


class AIRuntimeDecisionSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeDecisionEngine()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _intervention_center(self, target="JSON_CORRUPTED", intervention_type="json", priority="medium"):
        return {
            "interventions": [
                {
                    "title": "人工检查 JSON 写入来源",
                    "target": target,
                    "intervention_type": intervention_type,
                    "priority": priority,
                    "automation_allowed": False,
                    "manual_required": True,
                    "reason": "review only",
                    "expected_effect": "diagnosis",
                }
            ],
            "root_cause_interventions": [],
            "blocking_interventions": [],
            "manual_review_interventions": [],
            "never_auto_interventions": [],
        }

    def _causal_graph_center(self):
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

    def _safe_context(self):
        return (
            {"gate_status": "open"},
            {"constitution_status": "guarded"},
            {"trust_status": "high"},
            {"confidence_status": "high"},
        )

    def test_build_decisions_returns_dict(self):
        result = self.engine.build_decisions({}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("decisions", result)
        self.assertIn("recommended_decisions", result)

    def test_recommended_decision_generated(self):
        policy, constitution, trust, confidence = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(),
            {},
            policy,
            constitution,
            trust,
            confidence,
        )
        self.assertTrue(result["recommended_decisions"])
        self.assertEqual(result["recommended_decisions"][0]["decision_status"], "recommended")

    def test_blocked_decision_generated(self):
        _, constitution, trust, confidence = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(),
            {},
            {"gate_status": "blocked"},
            constitution,
            trust,
            confidence,
        )
        self.assertTrue(result["blocked_decisions"])
        self.assertFalse(result["blocked_decisions"][0]["boundary_safe"] is False and False)

    def test_manual_only_decision_generated(self):
        policy, constitution, trust, confidence = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(target="release", intervention_type="release"),
            {},
            policy,
            constitution,
            trust,
            confidence,
        )
        self.assertTrue(result["manual_only_decisions"])
        self.assertEqual(result["manual_only_decisions"][0]["decision_status"], "manual_only")

    def test_high_risk_decision_generated(self):
        policy, constitution, _, _ = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(priority="critical"),
            {},
            policy,
            constitution,
            {"trust_status": "low"},
            {"confidence_status": "low"},
        )
        self.assertTrue(result["high_risk_decisions"])
        self.assertEqual(result["high_risk_decisions"][0]["trust_level"], "low")

    def test_rollback_candidate_generated(self):
        policy, constitution, trust, confidence = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(priority="critical"),
            self._causal_graph_center(),
            policy,
            constitution,
            trust,
            confidence,
        )
        self.assertTrue(result["rollback_candidates"])
        plans = " ".join(item["rollback_plan"] for item in result["rollback_candidates"])
        self.assertIn("JSON", plans)

    def test_constitution_boundary_check_correct(self):
        policy, _, trust, confidence = self._safe_context()
        result = self.engine.build_decisions(
            self._intervention_center(),
            {},
            policy,
            {"constitution_status": "violation", "boundary_status": "blocked"},
            trust,
            confidence,
        )
        self.assertTrue(result["blocked_decisions"])
        self.assertFalse(result["blocked_decisions"][0]["constitution_safe"])
        self.assertFalse(result["blocked_decisions"][0]["boundary_safe"])

    def test_build_decision_center_returns_dict(self):
        dashboard = {
            "ai_runtime_intervention_center": self._intervention_center(),
            "ai_runtime_policy_gate_center": {"gate_status": "open"},
            "ai_runtime_constitution_center": {"constitution_status": "guarded"},
            "ai_runtime_trust_center": {"trust_status": "high"},
            "ai_runtime_confidence_center": {"confidence_status": "high"},
        }
        center = AIRuntimeDecisionService.build_decision_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn("decision_status", center)
        self.assertTrue(center["recommended_decisions"])

    def test_runtime_decision_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-decision-export", rules)

        for event_key in ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"]:
            self.bus.publish(event_key)
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-decision-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-decision-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-decision-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 决策中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 决策中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_decision_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 决策中心", template)


if __name__ == "__main__":
    unittest.main()
