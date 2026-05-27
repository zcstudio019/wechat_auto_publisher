import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_intervention_planner import AIRuntimeInterventionPlanner
from services.ai_runtime_intervention_service import AIRuntimeInterventionService


class AIRuntimeInterventionSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.bus = AIRuntimeEventBus(self.event_path)
        self.planner = AIRuntimeInterventionPlanner()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _causal_graph(self):
        return {
            "root_causes": [
                {
                    "node_id": "JSON_CORRUPTED",
                    "severity": "critical",
                    "confidence": "high",
                    "frequency": 3,
                    "summary": "JSON corruption is propagating.",
                }
            ],
            "symptoms": [
                {
                    "node_id": "RELEASE_BLOCKED",
                    "severity": "critical",
                    "confidence": "medium",
                    "frequency": 1,
                    "summary": "Release blocked is downstream.",
                }
            ],
            "critical_paths": [
                {
                    "path": ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"],
                    "severity": "critical",
                    "confidence": "high",
                    "summary": "JSON_CORRUPTED -> RELEASE_BLOCKED",
                }
            ],
        }

    def test_planner_plan_returns_dict(self):
        result = self.planner.plan({}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("interventions", result)
        self.assertIn("pre_checks", result)
        self.assertIn("post_checks", result)

    def test_root_cause_intervention_generated(self):
        result = self.planner.plan(self._causal_graph(), {})
        items = result["root_cause_interventions"]
        self.assertTrue(items)
        self.assertEqual(items[0]["target"], "JSON_CORRUPTED")
        self.assertFalse(items[0]["automation_allowed"])
        self.assertTrue(items[0]["manual_required"])

    def test_symptom_intervention_generated(self):
        result = self.planner.plan(self._causal_graph(), {})
        targets = {item["target"] for item in result["symptom_interventions"]}
        self.assertIn("RELEASE_BLOCKED", targets)

    def test_blocking_intervention_generated(self):
        result = self.planner.plan(self._causal_graph(), {})
        items = result["blocking_interventions"]
        self.assertTrue(items)
        self.assertEqual(items[0]["priority"], "critical")
        self.assertIn("JSON_CORRUPTED", items[0]["target"])

    def test_manual_review_intervention_exists(self):
        result = self.planner.plan({}, {})
        targets = {item["target"] for item in result["manual_review_interventions"]}
        self.assertIn("release", targets)
        self.assertIn("approval", targets)

    def test_never_auto_intervention_exists(self):
        result = self.planner.plan({}, {})
        titles = {item["title"] for item in result["never_auto_interventions"]}
        self.assertIn("自动发布", titles)
        self.assertIn("自动审核", titles)
        self.assertTrue(all(not item["automation_allowed"] for item in result["never_auto_interventions"]))

    def test_sequence_correct(self):
        result = self.planner.plan(self._causal_graph(), {})
        sequence = result["intervention_sequence"]
        self.assertTrue(sequence[0].startswith("1."))
        self.assertIn("根因", sequence[0])
        self.assertIn("阻断链路", sequence[1])

    def test_build_intervention_center_returns_dict(self):
        dashboard = {"ai_runtime_causal_graph_center": self._causal_graph()}
        center = AIRuntimeInterventionService.build_intervention_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["intervention_status"], "critical")
        self.assertIn("root_cause_interventions", center)

    def test_runtime_intervention_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-intervention-export", rules)

        for event_key in ["JSON_CORRUPTED", "JSON_CORRUPTED", "JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"]:
            self.bus.publish(event_key)
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-intervention-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-intervention-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-intervention-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 干预计划中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 干预计划中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_intervention_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 干预计划中心", template)


if __name__ == "__main__":
    unittest.main()
