import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_governance_summary_service import AIRuntimeGovernanceSummaryService


class AIRuntimeGovernanceSummaryServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_runtime_capability_matrix": {
                "capabilities": [
                    {
                        "capability_key": "CAP_READONLY_ANALYSIS",
                        "title": "Readonly analysis",
                        "category": "Runtime Analysis",
                        "maturity": "stable",
                        "risk_level": "low",
                        "human_required": False,
                        "readonly": True,
                        "automation_allowed": True,
                        "summary": "Read-only runtime analysis.",
                    },
                    {
                        "capability_key": "CAP_HIGH_RISK_REVIEW",
                        "title": "High risk review",
                        "category": "Governance",
                        "maturity": "experimental",
                        "risk_level": "critical",
                        "human_required": True,
                        "readonly": True,
                        "automation_allowed": False,
                        "summary": "Human review required.",
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
                        "summary": "Forbidden release automation.",
                    },
                ],
                "human_required_capabilities": [
                    {
                        "capability_key": "CAP_HIGH_RISK_REVIEW",
                        "title": "High risk review",
                        "risk_level": "critical",
                        "human_required": True,
                        "summary": "Human review required.",
                    }
                ],
                "forbidden_capabilities": [
                    {
                        "capability_key": "CAP_FORBIDDEN_RELEASE",
                        "title": "Autonomous release",
                        "risk_level": "critical",
                        "maturity": "restricted",
                        "automation_allowed": False,
                        "summary": "Forbidden release automation.",
                    }
                ],
            },
            "ai_runtime_capability_governance": {
                "governance_status": "critical",
                "governed_capabilities": [
                    {
                        "capability_key": "CAP_HIGH_RISK_REVIEW",
                        "title": "High risk review",
                        "maturity": "experimental",
                        "risk_level": "critical",
                        "human_only": True,
                        "approval_required": True,
                        "forbidden": False,
                        "summary": "Human review required.",
                    },
                    {
                        "capability_key": "CAP_FORBIDDEN_RELEASE",
                        "title": "Autonomous release",
                        "maturity": "restricted",
                        "risk_level": "critical",
                        "human_only": True,
                        "approval_required": True,
                        "forbidden": True,
                        "summary": "Forbidden release automation.",
                    },
                ],
                "human_only_capabilities": [
                    {
                        "capability_key": "CAP_HIGH_RISK_REVIEW",
                        "title": "High risk review",
                        "risk_level": "critical",
                        "human_only": True,
                        "summary": "Human review required.",
                    }
                ],
                "forbidden_capabilities": [
                    {
                        "capability_key": "CAP_FORBIDDEN_RELEASE",
                        "title": "Autonomous release",
                        "risk_level": "critical",
                        "forbidden": True,
                        "summary": "Forbidden release automation.",
                    }
                ],
                "restricted_capabilities": [
                    {
                        "capability_key": "CAP_FORBIDDEN_RELEASE",
                        "title": "Autonomous release",
                        "risk_level": "critical",
                        "maturity": "restricted",
                        "summary": "Forbidden release automation.",
                    }
                ],
                "delegation_risks": [
                    {
                        "risk_key": "HIGH_RISK_OPEN",
                        "capability": "High risk review",
                        "risk_level": "critical",
                        "summary": "High risk capability requires governance review.",
                    }
                ],
            },
            "ai_runtime_policy_compiler": {
                "policy_conflicts": [
                    {
                        "conflict_key": "BOUNDARY_VS_AUTOMATION",
                        "source": "Boundary vs Automation",
                        "risk_level": "critical",
                        "summary": "Automation conflicts with boundary.",
                    }
                ],
            },
            "ai_runtime_policy_linter": {
                "linter_status": "critical",
                "critical_issues": [
                    {
                        "issue": "Forbidden automation",
                        "severity": "critical",
                        "policy": "POLICY_FORBID_AUTOMATION",
                        "recommendation": "Keep human review.",
                    }
                ],
                "warning_issues": [
                    {
                        "issue": "Duplicate policy",
                        "severity": "warning",
                        "policy": "POLICY_DUPLICATE",
                        "recommendation": "Review policy compiler output.",
                    }
                ],
                "conflicting_policies": [],
            },
            "ai_runtime_command_layer": {
                "recommended_commands": [
                    {
                        "command_key": "COMMAND_OPEN_HOME",
                        "title": "Open home",
                        "risk_level": "low",
                        "recommended_route": "/ai-dashboard/home",
                    }
                ],
                "high_priority_commands": [
                    {
                        "command_key": "COMMAND_REVIEW_HIGH_RISK_AUTOMATION",
                        "title": "Review high risk automation",
                        "risk_level": "critical",
                        "recommended_route": "/ai-dashboard",
                    }
                ],
                "human_review_commands": [
                    {
                        "command_key": "COMMAND_REVIEW_HIGH_RISK_AUTOMATION",
                        "title": "Review high risk automation",
                        "risk_level": "critical",
                        "recommended_route": "/ai-dashboard",
                    }
                ],
                "blocked_commands": [
                    {
                        "command_key": "COMMAND_REVIEW_HIGH_RISK_AUTOMATION",
                        "title": "Review high risk automation",
                        "risk_level": "critical",
                        "recommended_route": "/ai-dashboard",
                    }
                ],
            },
            "ai_runtime_governance_court_center": {
                "forbidden_domains": [
                    {
                        "title": "autonomous publish",
                        "risk_level": "critical",
                        "summary": "Forbidden governance domain.",
                    }
                ]
            },
            "ai_runtime_judgment_center": {},
            "ai_runtime_constitution_center": {},
            "ai_runtime_boundary_center": {},
        }

    def test_build_governance_summary_returns_dict(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("summary_status", center)
        self.assertIn("summary", center)

    def test_capability_governance_overview_exists(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center["capability_governance_overview"], dict)
        self.assertGreaterEqual(center["capability_governance_overview"]["total_capabilities"], 1)

    def test_high_risk_capabilities_is_list(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center["high_risk_capabilities"], list)
        self.assertTrue(center["high_risk_capabilities"])

    def test_human_only_capabilities_is_list(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center["human_only_capabilities"], list)
        self.assertTrue(center["human_only_capabilities"])

    def test_forbidden_capabilities_is_list(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center["forbidden_capabilities"], list)
        self.assertTrue(center["forbidden_capabilities"])

    def test_delegation_risks_is_list(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        self.assertIsInstance(center["delegation_risks"], list)
        self.assertTrue(center["delegation_risks"])

    def test_policy_conflicts_summary_is_valid(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        policy_summary = center["policy_conflicts_summary"]
        self.assertIsInstance(policy_summary, dict)
        self.assertGreaterEqual(policy_summary["conflict_count"], 1)
        self.assertGreaterEqual(policy_summary["critical_count"], 1)

    def test_command_layer_summary_is_valid(self):
        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        command_summary = center["command_layer_summary"]
        self.assertIsInstance(command_summary, dict)
        self.assertEqual(command_summary["blocked_count"], 1)
        self.assertEqual(command_summary["high_priority_count"], 1)

    def test_governance_summary_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeGovernanceSummaryService.build_governance_summary(self._dashboard_fixture())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/governance-summary-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_governance_summary": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/governance-summary-export?format=txt")
                csv_response = client.get("/ai-dashboard/governance-summary-export?format=csv")
                md_response = client.get("/ai-dashboard/governance-summary-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime 治理汇总中心".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("类别".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 治理汇总中心".encode("utf-8"), md_response.data)

    def test_ai_dashboard_page_keeps_governance_summary_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 治理汇总中心", template)
        self.assertIn("/ai-dashboard/governance-summary-export?format=txt", template)

    def test_no_automatic_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_governance_summary_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def apply",
            "def dispatch",
            "def run",
            "subprocess",
            "publish_approved_articles",
            "scheduler",
            "worker",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
