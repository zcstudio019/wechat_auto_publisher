import unittest

from services.ai_runtime_metacognition_engine import AIRuntimeMetaCognitionEngine
from services.ai_runtime_metacognition_service import AIRuntimeMetaCognitionService


class AIRuntimeMetaCognitionSystemTest(unittest.TestCase):
    def setUp(self):
        self.engine = AIRuntimeMetaCognitionEngine()

    def _memory_center(self):
        return {
            "memory_status": "critical",
            "recent_memories": [{"title": "short memory"}],
            "repeated_patterns": [
                {"title": "recurring instability", "severity": "critical", "summary": "JSON risk"},
                {"title": "recurring event storm", "severity": "high", "summary": "storm risk"},
            ],
            "governance_lessons": [
                {"title": "boundary too weak", "severity": "critical", "summary": "boundary risk"},
                {"title": "policy gate should precede automation", "severity": "high", "summary": "gate first"},
            ],
            "stability_lessons": [
                {"title": "JSON dependency increases fragility", "severity": "critical", "summary": "json fragile"},
            ],
            "strategic_lessons": [
                {"title": "stability before automation", "severity": "critical", "summary": "stability first"},
            ],
            "organizational_wisdom": [
                {"title": "高 confidence 不代表高 safety", "severity": "high", "summary": "confidence is not safety"},
                {"title": "治理缺失比功能缺失更危险", "severity": "critical", "summary": "governance matters"},
            ],
            "memory_clusters": [
                {"title": "JSON instability cluster", "severity": "critical", "summary": "json cluster"},
                {"title": "correlation learning cluster", "severity": "medium", "summary": "correlation cluster"},
            ],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "attention",
            "stability_roadmap": [
                {"stage": "L1", "title": "恢复 Runtime 基础稳定", "priority": "critical"},
            ],
            "automation_roadmap": [
                {"stage": "A1", "title": "observation automation", "priority": "medium"},
                {"stage": "A2", "title": "export automation", "priority": "medium"},
            ],
            "governance_roadmap": [
                {"stage": "G1", "title": "boundary strengthening", "priority": "high"},
            ],
            "technical_debt_risks": [
                {"title": "JSON coupling", "severity": "critical", "summary": "json coupling"},
                {"title": "export bottlenecks", "severity": "medium", "summary": "export bottleneck"},
            ],
        }

    def _decision_center(self):
        return {
            "decision_status": "critical",
            "manual_only_decisions": [],
            "high_risk_decisions": [{"title": "high risk decision"}],
            "blocked_decisions": [{"title": "blocked decision"}],
            "rollback_candidates": [],
        }

    def _simulation_center(self):
        return {
            "simulation_status": "stable",
            "simulations": [{"title": "observe intervention"}],
            "best_case_scenarios": [{"title": "ops improves"}],
            "worst_case_scenarios": [],
            "risk_propagation_forecasts": [],
            "rollback_impacts": [],
        }

    def _result(self):
        return self.engine.build_metacognition(
            self._memory_center(),
            self._strategy_center(),
            self._decision_center(),
            self._simulation_center(),
            {"trust_status": "low"},
            {"confidence_status": "high"},
        )

    def test_build_metacognition_returns_dict(self):
        result = self.engine.build_metacognition({}, {}, {}, {}, {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("metacognition_status", result)
        self.assertIn("self_awareness_summary", result)

    def test_blind_spots_generated(self):
        titles = {item["title"] for item in self._result()["blind_spots"]}
        self.assertIn("weak rollback awareness", titles)
        self.assertIn("missing human review assumptions", titles)

    def test_uncertainty_sources_generated(self):
        titles = {item["title"] for item in self._result()["uncertainty_sources"]}
        self.assertIn("insufficient event history", titles)
        self.assertIn("inconsistent trust evaluation", titles)

    def test_overconfidence_risks_generated(self):
        titles = {item["title"] for item in self._result()["overconfidence_risks"]}
        self.assertIn("confidence > trust", titles)
        self.assertIn("weak governance with high confidence", titles)

    def test_governance_gaps_generated(self):
        titles = {item["title"] for item in self._result()["governance_gaps"]}
        self.assertIn("boundary not enforced strongly enough", titles)
        self.assertIn("manual review chain incomplete", titles)

    def test_strategic_biases_generated(self):
        titles = {item["title"] for item in self._result()["strategic_biases"]}
        self.assertIn("automation expansion bias", titles)
        self.assertIn("governance postponed too long", titles)

    def test_fragile_assumptions_generated(self):
        titles = {item["title"] for item in self._result()["fragile_assumptions"]}
        self.assertIn("JSON storage assumed stable", titles)
        self.assertIn("correlation assumed causal", titles)

    def test_cognitive_conflicts_generated(self):
        titles = {item["title"] for item in self._result()["cognitive_conflicts"]}
        self.assertIn("high confidence + low trust", titles)
        self.assertIn("aggressive roadmap + fragile architecture", titles)

    def test_build_metacognition_center_returns_dict(self):
        dashboard = {
            "ai_runtime_memory_center": self._memory_center(),
            "ai_runtime_strategy_center": self._strategy_center(),
            "ai_runtime_decision_center": self._decision_center(),
            "ai_runtime_simulation_center": self._simulation_center(),
            "ai_runtime_trust_center": {"trust_status": "low"},
            "ai_runtime_confidence_center": {"confidence_status": "high"},
        }
        center = AIRuntimeMetaCognitionService.build_metacognition_center(dashboard)
        self.assertIsInstance(center, dict)
        self.assertEqual(center["metacognition_status"], "critical")
        self.assertTrue(center["overconfidence_risks"])

    def test_runtime_metacognition_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-metacognition-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-metacognition-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-metacognition-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-metacognition-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 元认知中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("问题".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 元认知中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_metacognition_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 元认知中心", template)


if __name__ == "__main__":
    unittest.main()
