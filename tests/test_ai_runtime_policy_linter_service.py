import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_policy_linter_service import AIRuntimePolicyLinterService


class AIRuntimePolicyLinterServiceTest(unittest.TestCase):
    def _compiler(self, policies=None, matrix=None):
        policies = policies if policies is not None else [
            {
                "policy_key": "POLICY_READ_ONLY",
                "source": "Runtime Baseline",
                "category": "read_only",
                "risk_level": "low",
                "human_required": False,
                "status": "allowed",
                "summary": "Read-only policy review.",
            },
            {
                "policy_key": "POLICY_HUMAN_RELEASE",
                "source": "Governance Court",
                "category": "human_only",
                "risk_level": "critical",
                "human_required": True,
                "status": "blocked",
                "summary": "Release authorization requires humans.",
            },
        ]
        matrix = matrix if matrix is not None else [
            {
                "Layer": "read_only",
                "Policy": "POLICY_READ_ONLY",
                "Allowed": True,
                "Restricted": False,
                "Forbidden": False,
                "HumanOnly": False,
                "RiskLevel": "low",
                "Source": "Runtime Baseline",
            },
            {
                "Layer": "human_only",
                "Policy": "POLICY_HUMAN_RELEASE",
                "Allowed": False,
                "Restricted": False,
                "Forbidden": True,
                "HumanOnly": True,
                "RiskLevel": "critical",
                "Source": "Governance Court",
            },
        ]
        return {
            "ai_runtime_policy_compiler": {
                "compiled_policies": policies,
                "policy_matrix": matrix,
                "policy_conflicts": [],
            }
        }

    def test_build_policy_linter_returns_dict(self):
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler())
        self.assertIsInstance(linter, dict)
        self.assertIn("linter_status", linter)

    def test_clean_status_can_be_generated(self):
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler())
        self.assertEqual(linter["linter_status"], "clean")
        self.assertFalse(linter["lint_issues"])

    def test_duplicate_policy_can_be_detected(self):
        policies = [
            {"policy_key": "POLICY_DUP", "source": "A", "risk_level": "low", "human_required": False, "status": "allowed", "summary": "one"},
            {"policy_key": "POLICY_DUP", "source": "A", "risk_level": "low", "human_required": False, "status": "allowed", "summary": "two"},
        ]
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler(policies=policies, matrix=[]))
        self.assertTrue(linter["duplicate_policies"])
        self.assertEqual(linter["linter_status"], "warning")

    def test_allowed_and_forbidden_conflict_can_be_detected(self):
        matrix = [{
            "Layer": "governance",
            "Policy": "POLICY_CONFLICT",
            "Allowed": True,
            "Restricted": False,
            "Forbidden": True,
            "HumanOnly": True,
            "RiskLevel": "critical",
            "Source": "Judgment",
        }]
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler(matrix=matrix))
        self.assertTrue(linter["invalid_matrix_rows"])
        self.assertEqual(linter["linter_status"], "critical")

    def test_high_risk_without_human_review_can_be_detected(self):
        policies = [{
            "policy_key": "POLICY_HIGH",
            "source": "Immune",
            "risk_level": "critical",
            "human_required": False,
            "status": "warning",
            "summary": "Critical risk should be reviewed.",
        }]
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler(policies=policies, matrix=[]))
        self.assertTrue(linter["human_review_gaps"])
        self.assertEqual(linter["linter_status"], "critical")

    def test_missing_source_can_be_detected(self):
        policies = [{
            "policy_key": "POLICY_NO_SOURCE",
            "source": "",
            "risk_level": "low",
            "human_required": False,
            "status": "allowed",
            "summary": "Missing source.",
        }]
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler(policies=policies, matrix=[]))
        self.assertTrue(linter["missing_source_policies"])
        self.assertEqual(linter["linter_status"], "critical")

    def test_invalid_matrix_rows_can_be_detected(self):
        matrix = [{
            "Layer": "",
            "Policy": "",
            "Allowed": False,
            "Restricted": False,
            "Forbidden": True,
            "HumanOnly": False,
            "RiskLevel": "",
            "Source": "",
        }]
        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler(matrix=matrix))
        self.assertTrue(linter["invalid_matrix_rows"])

    def test_runtime_policy_linter_export_route_registered(self):
        from web_ui.app import app

        linter = AIRuntimePolicyLinterService.build_policy_linter(self._compiler())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-policy-linter-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_policy_linter": linter}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-policy-linter-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-policy-linter-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-policy-linter-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime 策略静态检查器".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Policy".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 策略静态检查器".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_policy_linter_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 策略静态检查器", template)

    def test_no_automatic_policy_linter_logic_exists(self):
        service_source = Path("services/ai_runtime_policy_linter_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def apply",
            "def execute",
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
