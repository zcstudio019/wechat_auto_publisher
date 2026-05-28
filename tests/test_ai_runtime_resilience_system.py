import unittest

from services.ai_runtime_resilience_engine import AIRuntimeResilienceEngine
from services.ai_runtime_resilience_service import AIRuntimeResilienceService


class AIRuntimeResilienceSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeResilienceEngine()

    def _immune_center(self):
        return {
            "immune_status": "critical",
            "immune_health_score": 35,
            "systemic_risks": [{"title": "integrity failure escalation", "risk": "critical"}],
            "governance_corruption_risks": [{"title": "governance weakening under scaling pressure", "risk": "critical"}],
            "trust_decay_patterns": [{"title": "confidence rising while trust falling", "risk": "critical"}],
            "fragility_patterns": [{"title": "high coupling runtime and governance dependency", "risk": "high"}],
            "dangerous_automation_patterns": [{"title": "self-expanding automation", "risk": "critical"}],
            "high_risk_mutations": [
                {"title": "civilization principle erosion", "risk": "critical"},
                {"title": "runtime identity instability", "risk": "high"},
            ],
        }

    def _adaptive_center(self):
        return {
            "adaptive_status": "critical",
            "adaptation_score": 40,
            "environment_change_signals": [
                {"title": "runtime complexity increasing", "risk": "high"},
                {"title": "automation expansion accelerating", "risk": "high"},
            ],
            "aging_governance_patterns": [{"title": "policy structure too rigid and slowing adaptation", "risk": "high"}],
            "civilization_rigidity_risks": [{"title": "governance too conservative", "risk": "medium"}],
            "long_term_survival_risks": [{"title": "automation growth exceeds adaptation and trust", "risk": "critical"}],
            "evolutionary_pressures": [{"title": "trust pressure", "risk": "critical"}],
        }

    def _integrity_center(self):
        return {
            "integrity_status": "critical",
            "integrity_score": 35,
            "governance_conflicts": [{"title": "policy conflicts with constitution", "risk": "critical"}],
            "value_fragmentations": [{"title": "human sovereignty identity conflict", "risk": "critical"}],
            "consistency_checks": [{"title": "judgment aligned with boundary", "risk": "low"}],
        }

    def _civilization_center(self):
        return {
            "civilization_status": "critical",
            "core_values": [{"title": "trust before delegation", "risk": "low"}],
            "human_first_principles": [{"title": "human approval required", "risk": "low"}],
            "governance_philosophies": [{"title": "bounded autonomy safer than unlimited autonomy", "risk": "low"}],
            "civilization_conflicts": [{"title": "constitution erosion risk", "risk": "critical"}],
        }

    def _intervention_center(self):
        return {
            "manual_review_interventions": [{"title": "governance review", "priority": "critical"}],
            "never_auto_interventions": [{"title": "never auto approval", "priority": "critical"}],
            "blocking_interventions": [{"title": "freeze release and block propagation", "priority": "critical"}],
            "post_checks": ["rollback release", "trust recovery", "governance post-check"],
        }

    def _simulation_center(self):
        return {
            "best_case_scenarios": [{"title": "trust improves after incident review", "risk_level": "low"}],
            "worst_case_scenarios": [{"title": "trust collapse under scaling", "risk_level": "critical"}],
            "rollback_impacts": [{"title": "release rollback available", "risk_level": "medium"}],
        }

    def _memory_center(self):
        return {
            "governance_lessons": [{"title": "shocks strengthen governance boundary", "risk": "high"}],
            "stability_lessons": [{"title": "architecture coupling fragility lesson", "risk": "high"}],
            "organizational_wisdom": [{"title": "trust requires manual review", "risk": "medium"}],
        }

    def _result(self):
        return self.engine.build_resilience_analysis(
            self._immune_center(),
            self._adaptive_center(),
            self._integrity_center(),
            self._civilization_center(),
            {"potential_risks": [{"title": "future trust collapse", "risk": "critical"}]},
            self._intervention_center(),
            self._simulation_center(),
            self._memory_center(),
        )

    def test_build_resilience_analysis_returns_dict(self):
        result = self.engine.build_resilience_analysis({}, {}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("resilience_status", result)
        self.assertIn("long_term_resilience_outlook", result)

    def test_resilience_score_generated(self):
        result = self._result()
        self.assertIsInstance(result["resilience_score"], int)
        self.assertLess(result["resilience_score"], 70)

    def test_fragility_patterns_generated(self):
        titles = {item["title"] for item in self._result()["fragility_patterns"]}
        self.assertIn("single governance dependency", titles)
        self.assertIn("trust-sensitive scaling", titles)

    def test_robustness_patterns_generated(self):
        titles = {item["title"] for item in self._result()["robustness_patterns"]}
        self.assertIn("bounded automation", titles)
        self.assertIn("stable governance structure", titles)

    def test_resilience_patterns_generated(self):
        titles = {item["title"] for item in self._result()["resilience_patterns"]}
        self.assertIn("system learns from failures", titles)
        self.assertIn("governance stabilizes after shocks", titles)

    def test_antifragile_patterns_generated(self):
        titles = {item["title"] for item in self._result()["antifragile_patterns"]}
        self.assertIn("shocks improve governance", titles)
        self.assertIn("failures improve architecture", titles)

    def test_collapse_risks_generated(self):
        titles = {item["title"] for item in self._result()["collapse_risks"]}
        self.assertIn("cascading governance failure", titles)
        self.assertIn("integrity collapse escalation", titles)

    def test_build_resilience_center_returns_dict(self):
        dashboard = {
            "ai_runtime_immune_center": self._immune_center(),
            "ai_runtime_adaptive_center": self._adaptive_center(),
            "ai_runtime_integrity_center": self._integrity_center(),
            "ai_runtime_civilization_center": self._civilization_center(),
            "ai_runtime_forecast_center": {"potential_risks": [{"title": "future trust collapse", "risk": "critical"}]},
            "ai_runtime_intervention_center": self._intervention_center(),
            "ai_runtime_simulation_center": self._simulation_center(),
            "ai_runtime_memory_center": self._memory_center(),
        }
        center = AIRuntimeResilienceService.build_resilience_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn(center["resilience_status"], {"fragile", "critical"})
        self.assertTrue(center["collapse_risks"])

    def test_runtime_resilience_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-resilience-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-resilience-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-resilience-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-resilience-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 韧性系统中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("韧性等级".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 韧性系统中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_resilience_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 韧性系统中心", template)


if __name__ == "__main__":
    unittest.main()
