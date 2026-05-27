import unittest

from services.ai_runtime_governance_court_engine import AIRuntimeGovernanceCourtEngine
from services.ai_runtime_governance_court_service import AIRuntimeGovernanceCourtService


class AIRuntimeGovernanceCourtSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeGovernanceCourtEngine()

    def _judgment_center(self):
        return {
            "judgment_status": "critical",
            "dangerous_automations": [
                {"title": "autonomous approval", "risk": "critical"},
                {"title": "autonomous publishing", "risk": "critical"},
                {"title": "autonomous policy override", "risk": "critical"},
            ],
            "unsafe_high_confidence_items": [
                {"title": "aggressive strategy under instability", "risk": "high"},
            ],
            "governance_violations": [
                {"title": "boundary not respected", "risk": "critical"},
                {"title": "policy gate ignored", "risk": "critical"},
            ],
            "long_term_rejections": [
                {"title": "autonomous governance rewrite", "risk": "critical"},
            ],
        }

    def _result(self):
        return self.engine.build_governance_court(
            self._judgment_center(),
            {"constitution_status": "unsafe"},
            {"boundary_status": "unsafe"},
            {"gate_status": "blocked"},
            {"trust_status": "low"},
            {"delegation_status": "paused"},
        )

    def test_build_governance_court_returns_dict(self):
        result = self.engine.build_governance_court({}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("court_status", result)
        self.assertIn("court_summary", result)

    def test_allowed_domains_generated(self):
        titles = {item["title"] for item in self._result()["allowed_domains"]}
        self.assertIn("reporting", titles)
        self.assertIn("dashboard analysis", titles)

    def test_restricted_domains_generated(self):
        titles = {item["title"] for item in self._result()["restricted_domains"]}
        self.assertIn("intervention recommendation", titles)
        self.assertIn("release preparation", titles)

    def test_forbidden_domains_generated(self):
        titles = {item["title"] for item in self._result()["forbidden_domains"]}
        self.assertIn("autonomous approval", titles)
        self.assertIn("autonomous publish", titles)

    def test_human_sovereignty_domains_generated(self):
        titles = {item["title"] for item in self._result()["human_sovereignty_domains"]}
        self.assertIn("release authorization", titles)
        self.assertIn("destructive operation", titles)

    def test_court_rulings_generated(self):
        titles = {item["title"] for item in self._result()["court_rulings"]}
        self.assertIn("automation expansion denied", titles)
        self.assertIn("runtime autonomy restricted", titles)

    def test_constitutional_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["constitutional_conflicts"]}
        self.assertIn("strategy conflicts with constitution", titles)
        self.assertIn("automation conflicts with boundary", titles)

    def test_governance_overrides_generated(self):
        titles = {item["title"] for item in self._result()["governance_overrides"]}
        self.assertIn("constitution overrides strategy", titles)
        self.assertIn("human sovereignty overrides delegation", titles)

    def test_build_governance_court_center_returns_dict(self):
        dashboard = {
            "ai_runtime_judgment_center": self._judgment_center(),
            "ai_runtime_constitution_center": {"constitution_status": "unsafe"},
            "ai_runtime_boundary_center": {"boundary_status": "unsafe"},
            "ai_runtime_policy_gate_center": {"gate_status": "blocked"},
            "ai_runtime_trust_center": {"trust_status": "low"},
            "ai_runtime_delegation_center": {"delegation_status": "paused"},
        }
        center = AIRuntimeGovernanceCourtService.build_governance_court_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["court_status"], "critical")
        self.assertTrue(center["permanent_prohibitions"])

    def test_runtime_governance_court_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-governance-court-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-governance-court-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-governance-court-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-governance-court-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 治理法庭中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("裁决".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 治理法庭中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_governance_court_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 治理法庭中心", template)


if __name__ == "__main__":
    unittest.main()
