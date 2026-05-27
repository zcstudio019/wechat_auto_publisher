import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_causal_graph_engine import AIRuntimeCausalGraphEngine
from services.ai_runtime_causal_graph_service import AIRuntimeCausalGraphService
from services.ai_runtime_event_bus import AIRuntimeEventBus


class AIRuntimeCausalGraphSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeCausalGraphEngine()

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

    def _critical_chain_events(self):
        return [
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("SMOKE_TEST_FAILED", severity="critical", layer="L7 Diagnostics Layer"),
            self._event("OPS_CRITICAL", severity="critical"),
            self._event("RELEASE_BLOCKED", severity="critical", layer="L9 Release Layer"),
        ]

    def test_build_graph_returns_dict(self):
        result = self.engine.build_graph([], [], [])
        self.assertIsInstance(result, dict)
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("root_causes", result)

    def test_root_cause_detected(self):
        result = self.engine.build_graph(self._critical_chain_events(), [], [])
        roots = {item["node_id"]: item for item in result["root_causes"]}
        self.assertIn("JSON_CORRUPTED", roots)
        self.assertEqual(roots["JSON_CORRUPTED"]["confidence"], "high")

    def test_symptom_detected(self):
        result = self.engine.build_graph(self._critical_chain_events(), [], [])
        symptoms = {item["node_id"] for item in result["symptoms"]}
        self.assertIn("RELEASE_BLOCKED", symptoms)

    def test_fragile_node_detected(self):
        result = self.engine.build_graph([
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("JSON_CORRUPTED", layer="L7 Diagnostics Layer"),
            self._event("SMOKE_TEST_FAILED", layer="L7 Diagnostics Layer"),
        ], [], [])
        fragile = {item["node_id"] for item in result["fragile_nodes"]}
        self.assertIn("JSON Store", fragile)

    def test_critical_path_generated(self):
        result = self.engine.build_graph(self._critical_chain_events(), [], [])
        self.assertTrue(result["critical_paths"])
        self.assertEqual(result["critical_paths"][0]["severity"], "critical")

    def test_edge_confidence_normal(self):
        result = self.engine.build_graph(self._critical_chain_events(), [], [])
        edge = next(
            item for item in result["edges"]
            if item["source"] == "JSON_CORRUPTED" and item["target"] == "SMOKE_TEST_FAILED"
        )
        self.assertEqual(edge["confidence"], "high")
        self.assertEqual(AIRuntimeCausalGraphEngine.confidence_for_count(2), "medium")

    def test_build_causal_graph_center_returns_dict(self):
        self.bus.publish("OPS_WARNING")
        center = AIRuntimeCausalGraphService.build_causal_graph_center(self.bus)
        self.assertIsInstance(center, dict)
        self.assertIn("causal_status", center)
        self.assertIn("root_causes", center)

    def test_critical_status_normal(self):
        for event_key in [
            "JSON_CORRUPTED",
            "JSON_CORRUPTED",
            "JSON_CORRUPTED",
            "SMOKE_TEST_FAILED",
            "OPS_CRITICAL",
            "RELEASE_BLOCKED",
        ]:
            self.bus.publish(event_key)
        center = AIRuntimeCausalGraphService.build_causal_graph_center(self.bus)
        self.assertEqual(center["causal_status"], "critical")

    def test_runtime_causal_graph_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-causal-graph-export", rules)

        for event_key in ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"]:
            self.bus.publish(event_key)
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-causal-graph-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-causal-graph-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-causal-graph-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 因果图谱中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 因果图谱中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_causal_graph_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 因果图谱中心", template)


if __name__ == "__main__":
    unittest.main()
