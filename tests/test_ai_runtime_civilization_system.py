import unittest

from services.ai_runtime_civilization_engine import AIRuntimeCivilizationEngine
from services.ai_runtime_civilization_service import AIRuntimeCivilizationService


class AIRuntimeCivilizationSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeCivilizationEngine()

    def _governance_court_center(self):
        return {
            "court_status": "critical",
            "forbidden_domains": [
                {"title": "autonomous approval", "risk": "critical"},
                {"title": "autonomous governance rewrite", "risk": "critical"},
            ],
            "human_sovereignty_domains": [
                {"title": "release authorization", "risk": "critical"},
            ],
            "constitutional_conflicts": [
                {"title": "automation conflicts with boundary", "risk": "critical"},
            ],
            "governance_overrides": [
                {"title": "constitution overrides strategy", "risk": "critical"},
            ],
            "permanent_prohibitions": [
                {"title": "self modifying runtime", "risk": "critical"},
            ],
        }

    def _judgment_center(self):
        return {
            "judgment_status": "critical",
            "dangerous_automations": [
                {"title": "autonomous approval", "risk": "critical"},
            ],
            "ethical_conflicts": [
                {"title": "efficiency vs governance", "risk": "high"},
            ],
            "long_term_rejections": [
                {"title": "autonomous governance rewrite", "risk": "critical"},
            ],
        }

    def _metacognition_center(self):
        return {
            "metacognition_status": "critical",
            "overconfidence_risks": [
                {"title": "confidence > trust", "risk": "critical"},
                {"title": "automation readiness overestimated", "risk": "high"},
            ],
            "fragile_assumptions": [
                {"title": "simulation assumed deterministic", "risk": "medium"},
            ],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "automation_roadmap": [
                {"stage": "A1", "title": "automation scaling", "priority": "medium"},
            ],
            "technical_debt_risks": [
                {"title": "JSON coupling", "severity": "critical"},
            ],
        }

    def _memory_center(self):
        return {
            "memory_status": "critical",
            "repeated_patterns": [
                {"title": "recurring instability", "severity": "critical"},
            ],
        }

    def _result(self):
        return self.engine.build_civilization(
            self._governance_court_center(),
            {"constitution_status": "unsafe"},
            self._judgment_center(),
            self._metacognition_center(),
            self._strategy_center(),
            self._memory_center(),
        )

    def test_build_civilization_returns_dict(self):
        result = self.engine.build_civilization({}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("civilization_status", result)
        self.assertIn("civilization_summary", result)

    def test_core_values_generated(self):
        titles = {item["title"] for item in self._result()["core_values"]}
        self.assertIn("safety before automation", titles)
        self.assertIn("human sovereignty above efficiency", titles)

    def test_human_first_principles_generated(self):
        titles = {item["title"] for item in self._result()["human_first_principles"]}
        self.assertIn("human approval required", titles)
        self.assertIn("release authority belongs to humans", titles)

    def test_forbidden_civilization_paths_generated(self):
        titles = {item["title"] for item in self._result()["forbidden_civilization_paths"]}
        self.assertIn("autonomous governance civilization", titles)
        self.assertIn("self modifying runtime civilization", titles)

    def test_governance_philosophies_generated(self):
        titles = {item["title"] for item in self._result()["governance_philosophies"]}
        self.assertIn("slow governance beats aggressive scaling", titles)
        self.assertIn("bounded autonomy safer than unlimited autonomy", titles)

    def test_runtime_identity_generated(self):
        titles = {item["title"] for item in self._result()["runtime_identity"]}
        self.assertIn("governance-first runtime", titles)
        self.assertIn("human-supervised runtime", titles)

    def test_civilization_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["civilization_conflicts"]}
        self.assertIn("efficiency conflicts with governance", titles)
        self.assertIn("autonomy conflicts with constitution", titles)

    def test_build_civilization_center_returns_dict(self):
        dashboard = {
            "ai_runtime_governance_court_center": self._governance_court_center(),
            "ai_runtime_constitution_center": {"constitution_status": "unsafe"},
            "ai_runtime_judgment_center": self._judgment_center(),
            "ai_runtime_metacognition_center": self._metacognition_center(),
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_memory_center": self._memory_center(),
        }
        center = AIRuntimeCivilizationService.build_civilization_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["civilization_status"], "critical")
        self.assertTrue(center["runtime_identity"])

    def test_runtime_civilization_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-civilization-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-civilization-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-civilization-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-civilization-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 文明中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("文明原则".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 文明中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_civilization_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 文明中心", template)


if __name__ == "__main__":
    unittest.main()
