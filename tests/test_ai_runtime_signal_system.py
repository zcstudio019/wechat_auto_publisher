import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_signal_engine import AIRuntimeSignalEngine
from services.ai_runtime_signal_intelligence_service import AIRuntimeSignalIntelligenceService
from services.ai_runtime_signal_registry import get_runtime_signal_definitions


class AIRuntimeSignalSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeSignalEngine()

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

    def test_signal_registry_not_empty(self):
        self.assertTrue(get_runtime_signal_definitions())

    def test_repeated_warnings_detected(self):
        analysis = self.engine.analyze_events([
            self._event("OPS_WARNING"),
            self._event("OPS_WARNING"),
            self._event("OPS_WARNING"),
        ])
        keys = {signal["signal_key"] for signal in analysis["signals"]}
        self.assertIn("REPEATED_WARNINGS", keys)

    def test_critical_cluster_detected(self):
        analysis = self.engine.analyze_events([
            self._event("OPS_CRITICAL", "critical"),
            self._event("SMOKE_TEST_FAILED", "critical"),
            self._event("RELEASE_BLOCKED", "critical"),
        ])
        keys = {signal["signal_key"] for signal in analysis["critical_signals"]}
        self.assertIn("CRITICAL_CLUSTER", keys)

    def test_recovery_loop_detected(self):
        analysis = self.engine.analyze_events([
            self._event("RUNTIME_DEGRADED"),
            self._event("RUNTIME_RECOVERED", "info"),
            self._event("RUNTIME_DEGRADED"),
            self._event("RUNTIME_RECOVERED", "info"),
        ])
        keys = {signal["signal_key"] for signal in analysis["signals"]}
        self.assertIn("RECOVERY_LOOP", keys)

    def test_event_storm_detected(self):
        analysis = self.engine.analyze_events([self._event("OPS_WARNING") for _ in range(20)])
        keys = {signal["signal_key"] for signal in analysis["signals"]}
        self.assertIn("EVENT_STORM", keys)

    def test_stability_score_normal(self):
        self.bus.publish("OPS_CRITICAL")
        self.bus.publish("OPS_WARNING")
        self.bus.publish("RUNTIME_RECOVERED")
        center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(self.bus)
        self.assertGreaterEqual(center["stability_score"], 0)
        self.assertLessEqual(center["stability_score"], 100)

    def test_build_signal_intelligence_returns_dict(self):
        self.bus.publish("OPS_WARNING")
        center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(self.bus)
        self.assertIsInstance(center, dict)
        self.assertIn("signal_status", center)
        self.assertIn("signals", center)

    def test_critical_signals_normal(self):
        self.bus.publish("OPS_CRITICAL")
        self.bus.publish("SMOKE_TEST_FAILED")
        self.bus.publish("RELEASE_BLOCKED")
        center = AIRuntimeSignalIntelligenceService.build_signal_intelligence(self.bus)
        keys = {signal["signal_key"] for signal in center["critical_signals"]}
        self.assertIn("CRITICAL_CLUSTER", keys)

    def test_runtime_signal_intelligence_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-signal-intelligence-export", rules)

        self.bus.publish("OPS_WARNING")
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-signal-intelligence-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-signal-intelligence-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-signal-intelligence-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 信号智能中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 信号智能中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_signal_intelligence_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 信号智能中心", template)


if __name__ == "__main__":
    unittest.main()
