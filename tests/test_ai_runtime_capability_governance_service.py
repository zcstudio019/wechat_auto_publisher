import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_capability_governance_service import AIRuntimeCapabilityGovernanceService


class AIRuntimeCapabilityGovernanceServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_capability_matrix": {
                "capabilities": [
                    {
                        "capability_key": "CAP_READONLY_NAV",
                        "title": "Readonly navigation",
                        "category": "Navigation",
                        "maturity": "stable",
                        "risk_level": "low",
                        "human_required": False,
                        "readonly": True,
                        "automation_allowed": True,
                        "summary": "Read-only routing.",
                    },
                    {
                        "capability_key": "CAP_ADVANCED_OPS",
                        "title": "Advanced ops analysis",
                        "category": "Runtime Analysis",
                        "maturity": "advanced",
                        "risk_level": "low",
                        "human_required": False,
                        "readonly": False,
                        "automation_allowed": True,
                        "summary": "Advanced runtime support.",
                    },
                    {
                        "capability_key": "CAP_HIGH_REVIEW",
                        "title": "High risk review",
                        "category": "Human Review",
                        "maturity": "experimental",
                        "risk_level": "high",
                        "human_required": True,
                        "readonly": True,
                        "automation_allowed": False,
                        "summary": "Review high risk automation.",
                    },
                    {
                        "capability_key": "CAP_FORBIDDEN_RELEASE",
                        "title": "Autonomous release",
                        "category": "Release Management",
                        "maturity": "restricted",
                        "risk_level": "critical",
                        "human_required": True,
                        "readonly": True,
                        "automation_allowed": False,
                        "summary": "Release approval remains human-only.",
                    },
                ],
                "forbidden_capabilities": [],
            }
        }

    def test_build_capability_governance_returns_dict(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        self.assertIsInstance(governance, dict)
        self.assertIn("governance_status", governance)

    def test_governed_capabilities_is_not_empty(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        self.assertTrue(governance["governed_capabilities"])

    def test_forbidden_capabilities_is_list(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        self.assertIsInstance(governance["forbidden_capabilities"], list)
        self.assertTrue(governance["forbidden_capabilities"])

    def test_approval_required_capabilities_is_list(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        self.assertIsInstance(governance["approval_required_capabilities"], list)
        self.assertTrue(governance["approval_required_capabilities"])

    def test_delegation_risks_is_list(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        self.assertIsInstance(governance["delegation_risks"], list)

    def test_role_recommendation_logic_is_correct(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        roles = {item["capability_key"]: item["recommended_role"] for item in governance["governed_capabilities"]}
        self.assertEqual(roles["CAP_FORBIDDEN_RELEASE"], "governance/admin")
        self.assertEqual(roles["CAP_HIGH_REVIEW"], "reviewer/governance")
        self.assertEqual(roles["CAP_READONLY_NAV"], "observer/readonly")
        self.assertEqual(roles["CAP_ADVANCED_OPS"], "ops/admin")

    def test_restricted_capability_can_be_identified(self):
        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        restricted = [item for item in governance["governed_capabilities"] if item["maturity"] == "restricted"]
        self.assertTrue(restricted)
        self.assertTrue(any(item["forbidden"] for item in restricted))

    def test_runtime_capability_governance_export_route_registered(self):
        from web_ui.app import app

        governance = AIRuntimeCapabilityGovernanceService.build_capability_governance(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-capability-governance-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_capability_governance": governance}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-capability-governance-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-capability-governance-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-capability-governance-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime OS 能力治理层".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Capability".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 能力治理层".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_capability_governance_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime OS 能力治理层", template)

    def test_no_automatic_capability_governance_logic_exists(self):
        service_source = Path("services/ai_runtime_capability_governance_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def apply",
            "def dispatch",
            "subprocess",
            "requests.",
            "publish_approved_articles",
            "worker",
            "scheduler",
            "login_required",
            "check_password",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
