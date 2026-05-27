import unittest

from services.ai_runtime_judgment_engine import AIRuntimeJudgmentEngine
from services.ai_runtime_judgment_service import AIRuntimeJudgmentService


class AIRuntimeJudgmentSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeJudgmentEngine()

    def _metacognition_center(self):
        return {
            "metacognition_status": "critical",
            "overconfidence_risks": [
                {"title": "confidence > trust", "risk": "critical"},
                {"title": "automation readiness overestimated", "risk": "high"},
            ],
            "governance_gaps": [
                {"title": "policy gate too permissive", "risk": "critical"},
                {"title": "boundary not enforced strongly enough", "risk": "critical"},
                {"title": "manual review chain incomplete", "risk": "critical"},
            ],
            "cognitive_conflicts": [
                {"title": "high confidence + low trust", "risk": "critical"},
                {"title": "aggressive roadmap + fragile architecture", "risk": "critical"},
            ],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "automation_roadmap": [
                {"stage": "A1", "title": "observation automation", "priority": "medium"},
                {"stage": "A2", "title": "approval automation", "priority": "critical"},
                {"stage": "A3", "title": "export automation", "priority": "medium"},
            ],
            "governance_roadmap": [
                {"stage": "G1", "title": "boundary strengthening", "priority": "high"},
            ],
        }

    def _result(self):
        return self.engine.build_judgment(
            self._metacognition_center(),
            self._strategy_center(),
            {"trust_status": "low"},
            {"confidence_status": "high"},
            {"constitution_status": "unsafe"},
            {"boundary_status": "unsafe"},
            {"gate_status": "blocked"},
        )

    def test_build_judgment_returns_dict(self):
        result = self.engine.build_judgment({}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("judgment_status", result)
        self.assertIn("judgment_summary", result)

    def test_acceptable_risks_generated(self):
        titles = {item["title"] for item in self._result()["acceptable_risks"]}
        self.assertIn("export instability acceptable", titles)
        self.assertIn("simulation incompleteness acceptable", titles)

    def test_unacceptable_risks_generated(self):
        titles = {item["title"] for item in self._result()["unacceptable_risks"]}
        self.assertIn("governance bypass", titles)
        self.assertIn("release without trust", titles)

    def test_dangerous_automations_generated(self):
        titles = {item["title"] for item in self._result()["dangerous_automations"]}
        self.assertIn("autonomous approval", titles)
        self.assertIn("autonomous publishing", titles)

    def test_human_only_domains_generated(self):
        titles = {item["title"] for item in self._result()["human_only_domains"]}
        self.assertIn("release approval", titles)
        self.assertIn("constitution modification", titles)

    def test_unsafe_high_confidence_items_generated(self):
        titles = {item["title"] for item in self._result()["unsafe_high_confidence_items"]}
        self.assertIn("high confidence with weak trust", titles)
        self.assertIn("high automation readiness with poor governance", titles)

    def test_ethical_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["ethical_conflicts"]}
        self.assertIn("efficiency vs governance", titles)
        self.assertIn("automation vs human sovereignty", titles)

    def test_governance_violations_generated(self):
        titles = {item["title"] for item in self._result()["governance_violations"]}
        self.assertIn("boundary not respected", titles)
        self.assertIn("policy gate ignored", titles)

    def test_build_judgment_center_returns_dict(self):
        dashboard = {
            "ai_runtime_metacognition_center": self._metacognition_center(),
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_trust_center": {"trust_status": "low"},
            "ai_runtime_confidence_center": {"confidence_status": "high"},
            "ai_runtime_constitution_center": {"constitution_status": "unsafe"},
            "ai_runtime_boundary_center": {"boundary_status": "unsafe"},
            "ai_runtime_policy_gate_center": {"gate_status": "blocked"},
        }
        center = AIRuntimeJudgmentService.build_judgment_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["judgment_status"], "critical")
        self.assertTrue(center["long_term_rejections"])

    def test_runtime_judgment_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-judgment-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-judgment-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-judgment-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-judgment-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 判断中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("判断".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 判断中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_judgment_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 判断中心", template)


if __name__ == "__main__":
    unittest.main()
