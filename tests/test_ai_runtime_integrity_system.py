import unittest

from services.ai_runtime_integrity_engine import AIRuntimeIntegrityEngine
from services.ai_runtime_integrity_service import AIRuntimeIntegrityService


class AIRuntimeIntegritySystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeIntegrityEngine()

    def _civilization_center(self):
        return {
            "civilization_status": "critical",
            "core_values": [{"title": "safety before automation", "risk": "critical"}],
            "human_first_principles": [{"title": "human approval required", "risk": "critical"}],
            "forbidden_civilization_paths": [
                {"title": "autonomous governance civilization", "risk": "critical"},
                {"title": "automation without rule of law civilization", "risk": "critical"},
            ],
            "governance_philosophies": [{"title": "bounded autonomy safer than unlimited autonomy", "risk": "critical"}],
            "civilization_conflicts": [{"title": "efficiency conflicts with governance", "risk": "critical"}],
        }

    def _governance_court_center(self):
        return {
            "court_status": "critical",
            "restricted_domains": [{"title": "delegation expansion", "risk": "critical"}],
            "forbidden_domains": [{"title": "autonomous governance rewrite", "risk": "critical"}],
            "court_rulings": [{"title": "automation expansion denied", "risk": "critical"}],
            "constitutional_conflicts": [{"title": "automation conflicts with boundary", "risk": "critical"}],
            "governance_overrides": [{"title": "constitution overrides strategy", "risk": "critical"}],
            "permanent_prohibitions": [{"title": "self modifying runtime", "risk": "critical"}],
        }

    def _judgment_center(self):
        return {
            "judgment_status": "critical",
            "acceptable_risks": [{"title": "simulation incompleteness acceptable", "risk": "medium"}],
            "dangerous_automations": [{"title": "autonomous approval", "risk": "critical"}],
            "ethical_conflicts": [{"title": "efficiency vs governance", "risk": "high"}],
            "governance_violations": [{"title": "boundary not respected", "risk": "critical"}],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "automation_roadmap": [
                {"stage": "A1", "title": "automation scaling", "priority": "high"},
                {"stage": "A2", "title": "self expanding automation", "priority": "critical"},
            ],
            "long_term_strategies": [{"title": "autonomous runtime expansion", "priority": "critical"}],
            "technical_debt_risks": [{"title": "Runtime coupling", "severity": "critical"}],
        }

    def _decision_center(self):
        return {"recommended_decisions": [{"title": "expand automation", "decision_status": "recommended"}]}

    def _metacognition_center(self):
        return {
            "uncertainty_sources": [{"title": "low confidence causal chain", "risk": "medium"}],
            "governance_gaps": [{"title": "governance roadmap missing", "risk": "critical"}],
            "overconfidence_risks": [{"title": "automation readiness overestimated", "risk": "high"}],
            "fragile_assumptions": [{"title": "simulation assumed deterministic", "risk": "medium"}],
        }

    def _result(self):
        return self.engine.build_integrity(
            self._civilization_center(),
            self._governance_court_center(),
            self._judgment_center(),
            self._strategy_center(),
            self._decision_center(),
            self._metacognition_center(),
            {"trust_status": "low"},
            {"boundary_status": "unsafe"},
        )

    def test_build_integrity_returns_dict(self):
        result = self.engine.build_integrity({}, {}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("integrity_status", result)
        self.assertIn("integrity_summary", result)

    def test_integrity_score_generated(self):
        result = self._result()
        self.assertIsInstance(result["integrity_score"], int)
        self.assertLess(result["integrity_score"], 70)

    def test_consistency_checks_generated(self):
        titles = {item["title"] for item in self._result()["consistency_checks"]}
        self.assertIn("strategy aligned with civilization", titles)
        self.assertIn("automation aligned with trust", titles)

    def test_governance_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["governance_conflicts"]}
        self.assertIn("policy conflicts with constitution", titles)
        self.assertIn("trust rules conflict with delegation", titles)

    def test_civilization_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["civilization_conflicts"]}
        self.assertIn("efficiency prioritized over safety", titles)
        self.assertIn("automation prioritized over sovereignty", titles)

    def test_cognitive_dissonance_generated(self):
        titles = {item["title"] for item in self._result()["cognitive_dissonance"]}
        self.assertIn("runtime wants autonomy but civilization forbids it", titles)
        self.assertIn("strategy promotes scaling while trust is declining", titles)

    def test_value_fragmentations_generated(self):
        titles = {item["title"] for item in self._result()["value_fragmentations"]}
        self.assertIn("governance values stability while strategy values scaling", titles)
        self.assertIn("human sovereignty conflicts with automation expansion", titles)

    def test_build_integrity_center_returns_dict(self):
        dashboard = {
            "ai_runtime_civilization_center": self._civilization_center(),
            "ai_runtime_governance_court_center": self._governance_court_center(),
            "ai_runtime_judgment_center": self._judgment_center(),
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_decision_center": self._decision_center(),
            "ai_runtime_metacognition_center": self._metacognition_center(),
            "ai_runtime_trust_center": {"trust_status": "low"},
            "ai_runtime_boundary_center": {"boundary_status": "unsafe"},
        }
        center = AIRuntimeIntegrityService.build_integrity_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn(center["integrity_status"], {"attention", "critical"})
        self.assertTrue(center["cognitive_dissonance"])

    def test_runtime_integrity_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-integrity-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-integrity-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-integrity-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-integrity-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 完整性中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("完整性".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 完整性中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_integrity_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 完整性中心", template)


if __name__ == "__main__":
    unittest.main()
