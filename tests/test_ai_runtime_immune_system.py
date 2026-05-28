import unittest

from services.ai_runtime_immune_engine import AIRuntimeImmuneEngine
from services.ai_runtime_immune_service import AIRuntimeImmuneService


class AIRuntimeImmuneSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeImmuneEngine()

    def _integrity_center(self):
        return {
            "integrity_status": "critical",
            "integrity_score": 32,
            "governance_conflicts": [{"title": "policy conflicts with constitution", "risk": "critical"}],
            "strategy_conflicts": [{"title": "runtime coupling and automation roadmap exceeds trust level", "risk": "critical"}],
            "trust_integrity_risks": [{"title": "low trust with high delegation", "risk": "critical"}],
            "value_fragmentations": [
                {"title": "governance values stability while strategy values scaling", "risk": "critical"},
                {"title": "human sovereignty conflicts with automation expansion", "risk": "critical"},
            ],
        }

    def _civilization_center(self):
        return {
            "civilization_status": "critical",
            "civilization_conflicts": [
                {"title": "efficiency conflicts with governance", "risk": "critical"},
                {"title": "optimization conflicts with sovereignty", "risk": "critical"},
            ],
            "forbidden_civilization_paths": [
                {"title": "self expanding autonomous governance civilization", "risk": "critical"},
                {"title": "scaling replacing governance", "risk": "high"},
            ],
            "runtime_identity": [{"title": "bounded-autonomy runtime", "risk": "high"}],
        }

    def _governance_court_center(self):
        return {
            "court_status": "critical",
            "restricted_domains": [{"title": "delegation expansion", "risk": "critical"}],
            "forbidden_domains": [{"title": "autonomous governance rewrite", "risk": "critical"}],
            "constitutional_conflicts": [{"title": "automation conflicts with boundary", "risk": "critical"}],
            "permanent_prohibitions": [{"title": "self modifying runtime", "risk": "critical"}],
        }

    def _judgment_center(self):
        return {
            "judgment_status": "critical",
            "dangerous_automations": [
                {"title": "autonomous governance modification", "risk": "critical"},
                {"title": "autonomous approval", "risk": "critical"},
            ],
            "ethical_conflicts": [
                {"title": "efficiency vs governance", "risk": "high"},
                {"title": "optimization vs human sovereignty", "risk": "high"},
            ],
            "governance_violations": [{"title": "boundary and policy ignored", "risk": "critical"}],
        }

    def _metacognition_center(self):
        return {
            "overconfidence_risks": [{"title": "confidence rising while trust is low", "risk": "critical"}],
            "governance_gaps": [
                {"title": "delegation automation governance gap", "risk": "critical"},
                {"title": "governance chain incomplete", "risk": "critical"},
            ],
            "fragile_assumptions": [{"title": "coupling assumed stable", "risk": "high"}],
        }

    def _result(self):
        return self.engine.build_immune_analysis(
            self._integrity_center(),
            self._civilization_center(),
            self._governance_court_center(),
            self._judgment_center(),
            {"trust_status": "low"},
            {"boundary_status": "unsafe"},
            self._metacognition_center(),
            {"signal_status": "critical"},
        )

    def test_build_immune_analysis_returns_dict(self):
        result = self.engine.build_immune_analysis({}, {}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("immune_status", result)
        self.assertIn("immune_summary", result)

    def test_immune_health_score_generated(self):
        result = self._result()
        self.assertIsInstance(result["immune_health_score"], int)
        self.assertLess(result["immune_health_score"], 70)

    def test_systemic_risks_generated(self):
        titles = {item["title"] for item in self._result()["systemic_risks"]}
        self.assertIn("governance collapse chain", titles)
        self.assertIn("integrity failure escalation", titles)

    def test_governance_corruption_risks_generated(self):
        titles = {item["title"] for item in self._result()["governance_corruption_risks"]}
        self.assertIn("automation bypassing governance", titles)
        self.assertIn("delegation expanding without trust", titles)

    def test_civilization_regression_risks_generated(self):
        titles = {item["title"] for item in self._result()["civilization_regression_risks"]}
        self.assertIn("efficiency replacing safety", titles)
        self.assertIn("optimization replacing sovereignty", titles)

    def test_dangerous_automation_patterns_generated(self):
        titles = {item["title"] for item in self._result()["dangerous_automation_patterns"]}
        self.assertIn("self-expanding automation", titles)
        self.assertIn("autonomous governance tendency", titles)

    def test_trust_decay_patterns_generated(self):
        titles = {item["title"] for item in self._result()["trust_decay_patterns"]}
        self.assertIn("confidence rising while trust falling", titles)
        self.assertIn("delegation increasing while trust unstable", titles)

    def test_build_immune_center_returns_dict(self):
        dashboard = {
            "ai_runtime_integrity_center": self._integrity_center(),
            "ai_runtime_civilization_center": self._civilization_center(),
            "ai_runtime_governance_court_center": self._governance_court_center(),
            "ai_runtime_judgment_center": self._judgment_center(),
            "ai_runtime_trust_center": {"trust_status": "low"},
            "ai_runtime_boundary_center": {"boundary_status": "unsafe"},
            "ai_runtime_metacognition_center": self._metacognition_center(),
            "ai_runtime_signal_intelligence": {"signal_status": "critical"},
        }
        center = AIRuntimeImmuneService.build_immune_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn(center["immune_status"], {"fragile", "critical"})
        self.assertTrue(center["high_risk_mutations"])

    def test_runtime_immune_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-immune-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-immune-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-immune-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-immune-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 免疫系统中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("免疫等级".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 免疫系统中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_immune_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 免疫系统中心", template)


if __name__ == "__main__":
    unittest.main()
