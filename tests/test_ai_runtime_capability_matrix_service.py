import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_capability_matrix_service import AIRuntimeCapabilityMatrixService


class AIRuntimeCapabilityMatrixServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_command_layer": {
                "command_layer_status": "normal",
                "recommended_commands": [
                    {
                        "command_key": "COMMAND_OPEN_HOME",
                        "title": "Open home",
                        "category": "navigation",
                        "risk_level": "low",
                        "human_required": False,
                        "recommended_route": "/ai-dashboard/home",
                        "description": "Open dashboard home.",
                    }
                ],
                "blocked_commands": [
                    {
                        "command_key": "COMMAND_REVIEW_HIGH_RISK_AUTOMATION",
                        "title": "Review high risk automation",
                        "category": "governance",
                        "risk_level": "critical",
                        "human_required": True,
                        "description": "Human review only.",
                    }
                ],
            },
            "ai_runtime_policy_compiler": {
                "compiled_policies": [
                    {
                        "policy_key": "POLICY_READ_ONLY",
                        "source": "Runtime Baseline",
                        "category": "read_only",
                        "risk_level": "low",
                        "human_required": False,
                        "status": "allowed",
                        "summary": "Read-only analysis allowed.",
                    },
                    {
                        "policy_key": "POLICY_RELEASE_HUMAN",
                        "source": "Governance Court",
                        "category": "human_only",
                        "risk_level": "critical",
                        "human_required": True,
                        "status": "blocked",
                        "summary": "Release approval remains human-only.",
                    },
                ],
                "policy_matrix": [],
            },
            "ai_runtime_policy_linter": {
                "linter_status": "clean",
                "lint_issues": [],
            },
            "ai_runtime_practical_console": {
                "console_status": "normal",
                "observe_today": [{"title": "Observe runtime", "priority": "low"}],
                "never_automate": [{"title": "Never auto publish", "priority": "critical"}],
            },
            "ai_runtime_mission_control_center": {
                "mission_status": "normal",
                "today_tasks": [{"title": "Review runtime status", "priority": "low"}],
            },
            "ai_runtime_decision_center": {
                "decision_status": "stable",
                "recommended_decisions": [{"title": "Observe only", "risk_level": "low"}],
            },
            "ai_runtime_simulation_center": {
                "simulation_status": "stable",
                "simulations": [{"title": "Rollback forecast", "risk_level": "low"}],
            },
            "ai_runtime_strategy_center": {
                "strategy_status": "stable",
                "short_term_strategies": [{"title": "Stability first", "risk_level": "low"}],
            },
            "ai_runtime_governance_court_center": {
                "court_status": "stable",
                "allowed_domains": [{"title": "Reporting", "risk_level": "low"}],
            },
            "ai_runtime_civilization_center": {
                "civilization_status": "stable",
                "core_values": [{"title": "Safety before automation", "risk_level": "low"}],
            },
            "ai_runtime_integrity_center": {
                "integrity_status": "stable",
                "consistency_checks": [{"title": "Strategy aligned", "risk_level": "low"}],
            },
            "ai_runtime_immune_center": {
                "immune_status": "stable",
                "immune_alerts": [],
            },
            "ai_runtime_adaptive_center": {
                "adaptive_status": "adaptive",
                "required_adaptations": [{"title": "Trust-aware scaling", "risk_level": "medium"}],
            },
            "ai_runtime_resilience_center": {
                "resilience_status": "resilient",
                "resilience_patterns": [{"title": "Recovery capability", "risk_level": "low"}],
            },
            "ai_runtime_evolutionary_fitness_center": {
                "fitness_status": "surviving",
                "high_fitness_structures": [{"title": "Governance-first structure", "risk_level": "low"}],
            },
        }

    def test_build_capability_matrix_returns_dict(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        self.assertIsInstance(matrix, dict)
        self.assertIn("matrix_status", matrix)

    def test_capabilities_is_not_empty(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        self.assertTrue(matrix["capabilities"])

    def test_readonly_capabilities_is_list(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        self.assertIsInstance(matrix["readonly_capabilities"], list)
        self.assertTrue(matrix["readonly_capabilities"])

    def test_forbidden_capabilities_is_list(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        self.assertIsInstance(matrix["forbidden_capabilities"], list)

    def test_unstable_capabilities_is_list(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        self.assertIsInstance(matrix["unstable_capabilities"], list)

    def test_maturity_classification_is_correct(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        maturities = {item["maturity"] for item in matrix["capabilities"]}
        self.assertIn("advanced", maturities)
        self.assertIn("restricted", maturities)

    def test_restricted_capability_can_be_identified(self):
        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        restricted = [item for item in matrix["capabilities"] if item["maturity"] == "restricted"]
        self.assertTrue(restricted)
        self.assertTrue(any(not item["automation_allowed"] for item in restricted))

    def test_runtime_capability_matrix_export_route_registered(self):
        from web_ui.app import app

        matrix = AIRuntimeCapabilityMatrixService.build_capability_matrix(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-capability-matrix-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_capability_matrix": matrix}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-capability-matrix-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-capability-matrix-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-capability-matrix-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime OS 能力矩阵".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Capability".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 能力矩阵".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_capability_matrix_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime OS 能力矩阵", template)

    def test_no_automatic_capability_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_capability_matrix_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def run",
            "def dispatch",
            "subprocess",
            "requests.",
            "publish_approved_articles",
            "worker",
            "scheduler",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
