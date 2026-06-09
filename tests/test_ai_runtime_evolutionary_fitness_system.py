import unittest

from services.ai_runtime_evolutionary_fitness_engine import AIRuntimeEvolutionaryFitnessEngine
from services.ai_runtime_evolutionary_fitness_service import AIRuntimeEvolutionaryFitnessService


class AIRuntimeEvolutionaryFitnessSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeEvolutionaryFitnessEngine()

    def _adaptive_center(self):
        return {
            "adaptive_status": "critical",
            "adaptation_score": 36,
            "environment_change_signals": [{"title": "runtime complexity increasing", "risk": "high"}],
            "aging_governance_patterns": [{"title": "policy structure too rigid and slowing adaptation", "risk": "high"}],
            "civilization_rigidity_risks": [{"title": "civilization resisting necessary evolution", "risk": "high"}],
            "cognitive_stagnation_patterns": [{"title": "repeated governance assumptions", "risk": "high"}],
            "long_term_survival_risks": [{"title": "automation growth exceeds adaptation and trust", "risk": "critical"}],
            "required_adaptations": [{"title": "bounded automation redesign", "risk": "critical"}],
            "evolutionary_pressures": [
                {"title": "scaling pressure", "risk": "high"},
                {"title": "trust pressure", "risk": "critical"},
                {"title": "governance pressure", "risk": "critical"},
            ],
        }

    def _resilience_center(self):
        return {
            "resilience_status": "critical",
            "resilience_score": 38,
            "recovery_capabilities": [{"title": "trust recovery", "resilience_level": "resilient"}],
            "fragility_patterns": [
                {"title": "over-centralized runtime", "risk": "high"},
                {"title": "trust-sensitive scaling", "risk": "critical"},
            ],
            "robustness_patterns": [{"title": "bounded automation", "resilience_level": "robust"}],
            "resilience_patterns": [{"title": "system learns from failures", "resilience_level": "resilient"}],
            "antifragile_patterns": [{"title": "shocks improve governance", "resilience_level": "antifragile"}],
            "collapse_risks": [{"title": "cascading governance failure", "risk": "critical"}],
        }

    def _civilization_center(self):
        return {
            "civilization_status": "critical",
            "core_values": [{"title": "trust before delegation", "risk": "low"}],
            "human_first_principles": [{"title": "human approval required", "risk": "low"}],
            "governance_philosophies": [{"title": "bounded autonomy safer than unlimited autonomy", "risk": "low"}],
            "forbidden_civilization_paths": [{"title": "uncontrolled autonomous automation", "risk": "critical"}],
            "civilization_conflicts": [{"title": "civilization legitimacy conflict", "risk": "critical"}],
        }

    def _integrity_center(self):
        return {
            "integrity_status": "critical",
            "integrity_score": 34,
            "governance_conflicts": [{"title": "policy conflicts with constitution", "risk": "critical"}],
            "strategy_conflicts": [{"title": "automation roadmap exceeds trust level", "risk": "critical"}],
            "trust_integrity_risks": [{"title": "low trust with high delegation", "risk": "critical"}],
            "value_fragmentations": [{"title": "human sovereignty identity conflict", "risk": "critical"}],
        }

    def _immune_center(self):
        return {
            "immune_status": "critical",
            "immune_health_score": 35,
            "systemic_risks": [{"title": "integrity failure escalation", "risk": "critical"}],
            "governance_corruption_risks": [{"title": "governance weakening under scaling pressure", "risk": "critical"}],
            "trust_decay_patterns": [{"title": "confidence rising while trust falling", "risk": "critical"}],
            "fragility_patterns": [{"title": "high coupling runtime", "risk": "high"}],
            "dangerous_automation_patterns": [{"title": "self-expanding automation", "risk": "critical"}],
            "high_risk_mutations": [
                {"title": "civilization principle erosion", "risk": "critical"},
                {"title": "runtime identity legitimacy instability", "risk": "critical"},
            ],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "automation_roadmap": [{"title": "automation scaling", "risk": "critical"}],
            "governance_roadmap": [{"title": "boundary and policy standardization", "risk": "high"}],
            "technical_debt_risks": [
                {"title": "centralized runtime dashboard dependency", "severity": "critical"},
                {"title": "recovery coupling debt", "severity": "high"},
            ],
        }

    def _governance_court_center(self):
        return {
            "court_status": "critical",
            "restricted_domains": [{"title": "delegation expansion", "risk": "critical"}],
            "human_sovereignty_domains": [{"title": "release authorization", "risk": "low"}],
            "governance_overrides": [{"title": "constitution overrides strategy", "risk": "low"}],
            "permanent_prohibitions": [{"title": "autonomous governance rewrite", "risk": "critical"}],
        }

    def _metacognition_center(self):
        return {
            "fragile_assumptions": [{"title": "governance assumed stable", "risk": "medium"}],
            "strategic_biases": [{"title": "governance rigidity bias", "risk": "high"}],
            "cognitive_conflicts": [{"title": "strategy conflicts with governance", "risk": "high"}],
        }

    def _result(self):
        return self.engine.build_fitness_analysis(
            self._adaptive_center(),
            self._resilience_center(),
            self._civilization_center(),
            self._integrity_center(),
            self._immune_center(),
            self._strategy_center(),
            self._governance_court_center(),
            self._metacognition_center(),
        )

    def test_build_fitness_analysis_returns_dict(self):
        result = self.engine.build_fitness_analysis({}, {}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("fitness_status", result)
        self.assertIn("evolutionary_summary", result)

    def test_fitness_score_generated(self):
        result = self._result()
        self.assertIsInstance(result["fitness_score"], int)
        self.assertLess(result["fitness_score"], 70)

    def test_high_fitness_structures_generated(self):
        titles = {item["title"] for item in self._result()["high_fitness_structures"]}
        self.assertIn("bounded governance", titles)
        self.assertIn("layered constitutional protection", titles)

    def test_low_fitness_structures_generated(self):
        titles = {item["title"] for item in self._result()["low_fitness_structures"]}
        self.assertIn("centralized fragile runtime", titles)
        self.assertIn("trust-dependent scaling", titles)

    def test_survival_advantages_generated(self):
        titles = {item["title"] for item in self._result()["survival_advantages"]}
        self.assertIn("strong resilience adaptation", titles)
        self.assertIn("bounded automation survival advantage", titles)

    def test_evolutionary_risks_generated(self):
        titles = {item["title"] for item in self._result()["evolutionary_risks"]}
        self.assertIn("governance rigidity", titles)
        self.assertIn("adaptation collapse", titles)

    def test_extinction_risks_generated(self):
        titles = {item["title"] for item in self._result()["extinction_risks"]}
        self.assertIn("civilization legitimacy collapse", titles)
        self.assertIn("adaptive failure cascade", titles)

    def test_build_evolutionary_fitness_center_returns_dict(self):
        dashboard = {
            "ai_runtime_adaptive_center": self._adaptive_center(),
            "ai_runtime_resilience_center": self._resilience_center(),
            "ai_runtime_civilization_center": self._civilization_center(),
            "ai_runtime_integrity_center": self._integrity_center(),
            "ai_runtime_immune_center": self._immune_center(),
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_governance_court_center": self._governance_court_center(),
            "ai_runtime_metacognition_center": self._metacognition_center(),
        }
        center = AIRuntimeEvolutionaryFitnessService.build_evolutionary_fitness_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn(center["fitness_status"], {"unstable evolution", "extinction risk"})
        self.assertTrue(center["selection_pressures"])

    def test_runtime_evolutionary_fitness_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-evolutionary-fitness-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-evolutionary-fitness-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-evolutionary-fitness-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-evolutionary-fitness-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 演化适应度中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("适应度".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 演化适应度中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_evolutionary_fitness_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 演化适应度中心", template)


if __name__ == "__main__":
    unittest.main()
