import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_event_registry import get_runtime_event_definitions
from services.ai_runtime_event_timeline_service import AIRuntimeEventTimelineService
from services.ai_runtime_layer_registry import get_runtime_center_manifests
from services.ai_runtime_os_kernel import AIRuntimeOSKernel


class AIRuntimeEventSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _dashboard_fixture(self):
        dashboard = {item["key"]: {"summary": "ok"} for item in get_runtime_center_manifests()}
        dashboard["ai_dashboard_ops_health_center"] = {
            "ops_status": "critical",
            "smoke_test_status": {"status": "failed"},
        }
        dashboard["ai_dashboard_export_operations_center"] = {"operations_status": "normal"}
        dashboard["ai_dashboard_release_readiness_center"] = {"release_status": "ready"}
        dashboard["ai_runtime_trust_center"] = {"trust_status": "normal"}
        dashboard["ai_runtime_boundary_center"] = {"boundary_status": "safe"}
        dashboard["ai_runtime_policy_gate_center"] = {"gate_status": "open"}
        return dashboard

    def test_event_registry_not_empty(self):
        self.assertTrue(get_runtime_event_definitions())

    def test_publish_normal(self):
        event = self.bus.publish("OPS_WARNING", {"status": "warning"})
        self.assertEqual(event["event_key"], "OPS_WARNING")
        self.assertEqual(event["severity"], "warning")

    def test_recent_events_normal(self):
        self.bus.publish("OPS_WARNING")
        self.bus.publish("OPS_CRITICAL")
        recent = self.bus.get_recent_events(limit=2)
        self.assertEqual([event["event_key"] for event in recent], ["OPS_CRITICAL", "OPS_WARNING"])

    def test_severity_filter_normal(self):
        self.bus.publish("OPS_WARNING")
        self.bus.publish("OPS_CRITICAL")
        critical = self.bus.get_events_by_severity("critical")
        self.assertEqual(len(critical), 1)
        self.assertEqual(critical[0]["event_key"], "OPS_CRITICAL")

    def test_layer_filter_normal(self):
        self.bus.publish("OPS_WARNING")
        self.bus.publish("RELEASE_BLOCKED")
        events = self.bus.get_events_by_layer("L9 Release Layer")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_key"], "RELEASE_BLOCKED")

    def test_clear_old_events_normal(self):
        for index in range(6):
            self.bus.publish("OPS_WARNING", {"index": index})
        kept = self.bus.clear_old_events(max_keep=3)
        self.assertEqual(len(kept), 3)
        self.assertEqual(len(self.bus.get_recent_events(limit=10)), 3)

    def test_json_corruption_fallback(self):
        self.event_path.write_text("{bad json", encoding="utf-8")
        self.assertEqual(self.bus.get_recent_events(), [])
        self.bus.publish("JSON_CORRUPTED")
        self.assertEqual(self.bus.get_recent_events(limit=1)[0]["event_key"], "JSON_CORRUPTED")

    def test_timeline_build_returns_dict(self):
        self.bus.publish("OPS_WARNING")
        timeline = AIRuntimeEventTimelineService.build_event_timeline(self.bus)
        self.assertIsInstance(timeline, dict)
        self.assertEqual(timeline["timeline_status"], "warning")
        self.assertTrue(timeline["warning_events"])

    def test_kernel_can_generate_events(self):
        AIRuntimeOSKernel.build_kernel_view(self._dashboard_fixture(), event_bus=self.bus)
        event_keys = {event["event_key"] for event in self.bus.get_recent_events(limit=10)}
        self.assertIn("OPS_CRITICAL", event_keys)
        self.assertIn("SMOKE_TEST_FAILED", event_keys)

    def test_runtime_event_timeline_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-event-timeline-export", rules)

        self.bus.publish("OPS_WARNING")
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-event-timeline-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-event-timeline-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-event-timeline-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 事件时间线】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 事件时间线".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_event_timeline_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 事件时间线", template)


if __name__ == "__main__":
    unittest.main()
