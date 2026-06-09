import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_policy_compiler_service import AIRuntimePolicyCompilerService


class AIRuntimePolicyCompilerServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_constitution_center": {
                "constitution_status": "stable",
                "principles": [{"title": "human approval required", "risk_level": "low"}],
            },
            "ai_runtime_boundary_center": {
                "boundary_status": "warning",
                "forbidden_actions": [{"title": "no autonomous publish", "risk_level": "critical"}],
            },
            "ai_runtime_judgment_center": {
                "judgment_status": "attention",
                "dangerous_automations": [{"title": "autonomous approval", "risk_level": "critical"}],
                "governance_violations": [{"title": "policy gate ignored", "risk_level": "critical"}],
            },
            "ai_runtime_governance_court_center": {
                "court_status": "attention",
                "forbidden_domains": [{"title": "autonomous publish", "risk_level": "critical"}],
                "human_sovereignty_domains": [{"title": "release authorization", "risk_level": "critical"}],
            },
            "ai_runtime_civilization_center": {
                "civilization_status": "attention",
                "core_values": [{"title": "safety before automation", "risk_level": "low"}],
                "civilization_conflicts": [{"title": "efficiency conflicts with governance", "risk_level": "high"}],
            },
            "ai_runtime_integrity_center": {
                "integrity_status": "attention",
                "integrity_score": 62,
                "strategy_conflicts": [{"title": "automation roadmap exceeds trust", "risk_level": "high"}],
                "cognitive_dissonance": [{"title": "strategy scales while trust falls", "risk_level": "high"}],
            },
            "ai_runtime_immune_center": {
                "immune_status": "critical",
                "immune_alerts": [{"title": "trust collapse propagation", "risk_level": "critical"}],
                "high_risk_mutations": [{"title": "runtime identity instability", "risk_level": "critical"}],
            },
            "ai_runtime_strategy_center": {
                "automation_roadmap": [{"title": "observation automation", "risk_level": "medium"}],
            },
            "ai_runtime_adaptive_center": {
                "required_adaptations": [{"title": "trust-aware scaling", "risk_level": "medium"}],
            },
            "ai_runtime_evolutionary_fitness_center": {
                "extinction_risks": [{"title": "governance extinction", "risk_level": "critical"}],
            },
            "ai_runtime_command_layer": {
                "human_review_commands": [{"title": "review automation", "risk_level": "critical"}],
            },
        }

    def test_build_policy_compiler_returns_dict(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertIsInstance(compiler, dict)
        self.assertIn("compiler_status", compiler)

    def test_compiled_policies_is_not_empty(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertTrue(compiler["compiled_policies"])

    def test_policy_matrix_is_not_empty(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertTrue(compiler["policy_matrix"])
        self.assertIn("Layer", compiler["policy_matrix"][0])

    def test_policy_conflicts_is_list(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertIsInstance(compiler["policy_conflicts"], list)

    def test_human_only_policies_is_list(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertIsInstance(compiler["human_only_policies"], list)
        self.assertTrue(compiler["human_only_policies"])

    def test_blocked_policies_is_list(self):
        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        self.assertIsInstance(compiler["blocked_policies"], list)
        self.assertTrue(compiler["blocked_policies"])

    def test_runtime_policy_compiler_export_route_registered(self):
        from web_ui.app import app

        compiler = AIRuntimePolicyCompilerService.build_policy_compiler(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-policy-compiler-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_policy_compiler": compiler}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-policy-compiler-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-policy-compiler-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-policy-compiler-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime 策略编译器".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Policy".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 策略编译器".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_policy_compiler_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 策略编译器", template)

    def test_no_automatic_policy_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_policy_compiler_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def dispatch",
            "def apply",
            "subprocess",
            "requests.",
            "publish_approved_articles",
            "worker",
            "scheduler",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
