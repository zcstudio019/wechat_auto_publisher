import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_correlation_engine import AIRuntimeCorrelationEngine
from services.ai_runtime_correlation_service import AIRuntimeCorrelationService
from services.ai_runtime_event_bus import AIRuntimeEventBus


class AIRuntimeCorrelationSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeCorrelationEngine()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _event(self, event_key, severity="warning", layer="L4 Operations Layer"):
        return {
            "timestamp": "2026-05-27T00:00:00+00:00",
            "event_key": event_key,
            "severity": severity,
            "layer": layer,
            "description": event_key,
            "payload": {},
        }

    def test_analyze_returns_dict(self):
        result = self.engine.analyze([], [])
        self.assertIsInstance(result, dict)
        self.assertIn("correlations", result)
        self.assertIn("root_cause_candidates", result)

    def test_repeated_pair_detected(self):
        result = self.engine.analyze([
            self._event("OPS_WARNING"),
            self._event("EXPORT_FAILED", layer="L8 Export / Documentation Layer"),
            self._event("OPS_WARNING"),
            self._event("EXPORT_FAILED", layer="L8 Export / Documentation Layer"),
        ], [])
        repeated = [item for item in result["correlations"] if item["correlation_type"] == "repeated_pair"]
        self.assertTrue(repeated)
        self.assertEqual(repeated[0]["confidence"], "medium")

    def test_root_cause_candidate_detected(self):
        result = self.engine.analyze([
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("OPS_WARNING"),
        ], [])
        candidates = {item["candidate"] for item in result["root_cause_candidates"]}
        self.assertIn("JSON_CORRUPTED", candidates)

    def test_co_occurrence_detected(self):
        result = self.engine.analyze([
            self._event("RELEASE_BLOCKED", severity="critical", layer="L9 Release Layer"),
            self._event("OPS_CRITICAL", severity="critical"),
        ], [])
        pairs = {(item["source"], item["target"]) for item in result["co_occurrence_patterns"]}
        self.assertIn(("RELEASE_BLOCKED", "OPS_CRITICAL"), pairs)

    def test_impact_chain_generated(self):
        result = self.engine.analyze([
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("SMOKE_TEST_FAILED", severity="critical", layer="L7 Diagnostics Layer"),
            self._event("OPS_CRITICAL", severity="critical"),
            self._event("RELEASE_BLOCKED", severity="critical", layer="L9 Release Layer"),
        ], [])
        self.assertTrue(result["impact_chains"])
        self.assertEqual(result["impact_chains"][0]["severity"], "critical")

    def test_confidence_calculation_correct(self):
        self.assertEqual(AIRuntimeCorrelationEngine.confidence_for_count(1), "low")
        self.assertEqual(AIRuntimeCorrelationEngine.confidence_for_count(2), "medium")
        self.assertEqual(AIRuntimeCorrelationEngine.confidence_for_count(3), "high")

    def test_build_correlation_center_returns_dict(self):
        self.bus.publish("OPS_WARNING")
        center = AIRuntimeCorrelationService.build_correlation_center(self.bus)
        self.assertIsInstance(center, dict)
        self.assertIn("correlation_status", center)
        self.assertIn("correlations", center)

    def test_status_attention_and_critical_normal(self):
        self.bus.publish("EXPORT_FAILED")
        self.bus.publish("OPS_WARNING")
        attention_center = AIRuntimeCorrelationService.build_correlation_center(self.bus)
        self.assertEqual(attention_center["correlation_status"], "attention")

        critical_bus = AIRuntimeEventBus(Path(self.tmpdir.name) / "critical_events.json")
        critical_bus.publish("JSON_CORRUPTED")
        critical_bus.publish("JSON_CORRUPTED")
        critical_bus.publish("JSON_CORRUPTED")
        critical_bus.publish("OPS_WARNING")
        critical_center = AIRuntimeCorrelationService.build_correlation_center(critical_bus)
        self.assertEqual(critical_center["correlation_status"], "critical")

    def test_runtime_correlation_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-correlation-export", rules)

        self.bus.publish("EXPORT_FAILED")
        self.bus.publish("OPS_WARNING")
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-correlation-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-correlation-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-correlation-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 关联分析中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 关联分析中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_correlation_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 关联分析中心", template)


if __name__ == "__main__":
    unittest.main()
