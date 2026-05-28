import unittest

from services.ai_runtime_adaptive_engine import AIRuntimeAdaptiveEngine
from services.ai_runtime_adaptive_service import AIRuntimeAdaptiveService


class AIRuntimeAdaptiveSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeAdaptiveEngine()

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "automation_roadmap": [
                {"title": "automation scaling", "risk": "high"},
                {"title": "trust-aware automation missing", "risk": "critical"},
            ],
            "long_term_strategies": [{"title": "stability and governance roadmap", "risk": "high"}],
            "technical_debt_risks": [
                {"title": "Runtime coupling and dashboard dependency", "severity": "critical"},
                {"title": "governance debt", "severity": "critical"},
            ],
        }

    def _civilization_center(self):
        return {
            "civilization_status": "critical",
            "forbidden_civilization_paths": [{"title": "uncontrolled automation scaling", "risk": "critical"}],
            "governance_philosophies": [{"title": "slow bounded governance", "risk": "medium"}],
            "civilization_conflicts": [{"title": "adaptation blocked by governance rigidity", "risk": "high"}],
        }

    def _integrity_center(self):
        return {
            "integrity_status": "attention",
            "integrity_score": 48,
            "strategy_conflicts": [{"title": "automation roadmap exceeds trust level", "risk": "critical"}],
        }

    def _immune_center(self):
        return {
            "immune_status": "critical",
            "immune_health_score": 42,
            "governance_corruption_risks": [{"title": "governance weakening under scaling pressure", "risk": "critical"}],
            "trust_decay_patterns": [{"title": "confidence rising while trust falling", "risk": "critical"}],
            "fragility_patterns": [{"title": "high coupling runtime", "risk": "high"}],
            "dangerous_automation_patterns": [{"title": "self-expanding automation", "risk": "critical"}],
            "civilization_regression_risks": [{"title": "efficiency replacing safety", "risk": "critical"}],
            "systemic_risks": [{"title": "governance collapse chain", "risk": "critical"}],
        }

    def _metacognition_center(self):
        return {
            "governance_gaps": [
                {"title": "missing governance chain", "risk": "critical"},
                {"title": "adaptation blocked by missing policy", "risk": "high"},
            ],
            "strategic_biases": [{"title": "governance postponed and rigid", "risk": "high"}],
            "fragile_assumptions": [{"title": "governance assumed stable", "risk": "medium"}],
        }

    def _memory_center(self):
        return {
            "governance_lessons": [{"title": "boundary weak and governance rules outdated", "risk": "high"}],
            "strategic_lessons": [{"title": "stability before automation", "risk": "high"}],
            "repeated_patterns": [{"title": "recurring event storm loop", "risk": "high"}],
            "organizational_wisdom": [{"title": "manual approval required", "risk": "medium"}],
        }

    def _forecast_center(self):
        return {
            "forecast_status": "warning",
            "potential_risks": [{"title": "future governance complexity", "risk": "high"}],
        }

    def _result(self):
        return self.engine.build_adaptive_analysis(
            self._strategy_center(),
            self._civilization_center(),
            self._integrity_center(),
            self._immune_center(),
            self._metacognition_center(),
            self._memory_center(),
            self._forecast_center(),
            {"signal_status": "critical"},
        )

    def test_build_adaptive_analysis_returns_dict(self):
        result = self.engine.build_adaptive_analysis({}, {}, {}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("adaptive_status", result)
        self.assertIn("adaptive_summary", result)

    def test_adaptation_score_generated(self):
        result = self._result()
        self.assertIsInstance(result["adaptation_score"], int)
        self.assertLess(result["adaptation_score"], 70)

    def test_environment_change_signals_generated(self):
        titles = {item["title"] for item in self._result()["environment_change_signals"]}
        self.assertIn("runtime complexity increasing", titles)
        self.assertIn("governance pressure rising", titles)

    def test_aging_governance_patterns_generated(self):
        titles = {item["title"] for item in self._result()["aging_governance_patterns"]}
        self.assertIn("governance rules outdated", titles)
        self.assertIn("policy structure too rigid", titles)

    def test_strategic_obsolescence_risks_generated(self):
        titles = {item["title"] for item in self._result()["strategic_obsolescence_risks"]}
        self.assertIn("roadmap incompatible with trust level", titles)
        self.assertIn("governance model cannot scale", titles)

    def test_cognitive_stagnation_patterns_generated(self):
        titles = {item["title"] for item in self._result()["cognitive_stagnation_patterns"]}
        self.assertIn("repeated governance assumptions", titles)
        self.assertIn("memory loops without evolution", titles)

    def test_evolutionary_pressures_generated(self):
        titles = {item["title"] for item in self._result()["evolutionary_pressures"]}
        self.assertIn("scaling pressure", titles)
        self.assertIn("trust pressure", titles)

    def test_build_adaptive_center_returns_dict(self):
        dashboard = {
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_civilization_center": self._civilization_center(),
            "ai_runtime_integrity_center": self._integrity_center(),
            "ai_runtime_immune_center": self._immune_center(),
            "ai_runtime_metacognition_center": self._metacognition_center(),
            "ai_runtime_memory_center": self._memory_center(),
            "ai_runtime_forecast_center": self._forecast_center(),
            "ai_runtime_signal_intelligence": {"signal_status": "critical"},
        }
        center = AIRuntimeAdaptiveService.build_adaptive_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertIn(center["adaptive_status"], {"rigid", "critical"})
        self.assertTrue(center["required_adaptations"])

    def test_runtime_adaptive_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-adaptive-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-adaptive-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-adaptive-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-adaptive-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 自适应系统中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("演化压力".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 自适应系统中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_adaptive_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 自适应系统中心", template)


if __name__ == "__main__":
    unittest.main()
