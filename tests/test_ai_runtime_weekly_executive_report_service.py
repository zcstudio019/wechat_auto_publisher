import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_weekly_executive_report_service import AIRuntimeWeeklyExecutiveReportService


class AIRuntimeWeeklyExecutiveReportServiceTest(unittest.TestCase):
    def _base_dashboard(self):
        return {
            "ai_runtime_daily_operator_brief": {
                "brief_status": "normal",
                "governance_risks_today": [],
            },
            "ai_runtime_one_page_console": {"console_status": "normal"},
            "ai_runtime_practical_console": {"console_status": "normal"},
            "ai_runtime_governance_summary": {
                "summary_status": "stable",
                "delegation_risks": [],
                "high_risk_capabilities": [],
                "human_only_capabilities": [],
            },
            "ai_dashboard_ops_health_center": {
                "ops_status": "healthy",
                "risk_items": [],
                "warning_items": [],
            },
            "ai_dashboard_release_readiness_center": {
                "release_status": "ready",
                "blocking_checks": [],
                "warning_checks": [],
                "passed_checks": [
                    {"title": "Smoke Test passed", "status": "passed", "summary": "Smoke test ok."}
                ],
            },
            "ai_dashboard_export_operations_center": {
                "operations_status": "normal",
                "warnings": [],
                "failed_items": [],
            },
            "ai_runtime_policy_linter": {
                "linter_status": "clean",
                "critical_issues": [],
                "warning_issues": [],
            },
            "ai_runtime_policy_compiler": {
                "policy_conflicts": [],
                "warning_policies": [],
            },
            "ai_runtime_capability_governance": {
                "governance_status": "stable",
                "forbidden_capabilities": [],
                "delegation_risks": [],
                "approval_required_capabilities": [],
            },
            "ai_runtime_capability_matrix": {
                "unstable_capabilities": [],
                "forbidden_capabilities": [],
                "capability_gaps": [],
            },
            "ai_runtime_command_layer": {
                "high_priority_commands": [],
                "human_review_commands": [],
            },
            "ai_runtime_judgment_center": {
                "governance_violations": [],
                "unacceptable_risks": [],
            },
            "ai_runtime_governance_court_center": {
                "constitutional_conflicts": [],
                "court_rulings": [],
            },
            "ai_dashboard_ops_maintenance_center": {
                "today_tasks": [],
                "recommended_actions": [],
            },
            "ai_dashboard_smoke_test_center": {
                "failed_checks": [],
                "warning_checks": [],
            },
            "ai_dashboard_release_package_center": {
                "package_items": [],
                "recommended_actions": [],
            },
            "ai_dashboard_release_runbook_center": {
                "runbook_steps": [],
                "recommended_actions": [],
            },
        }

    def _critical_dashboard(self):
        dashboard = self._base_dashboard()
        dashboard["ai_runtime_daily_operator_brief"]["brief_status"] = "urgent"
        dashboard["ai_runtime_daily_operator_brief"]["governance_risks_today"] = [
            {"title": "Critical delegation risk", "priority": "critical", "source": "Daily Brief", "reason": "Critical governance risk."}
        ]
        dashboard["ai_runtime_governance_summary"]["summary_status"] = "critical"
        dashboard["ai_runtime_governance_summary"]["delegation_risks"] = [
            {"title": "Delegation risk", "risk_level": "critical", "summary": "Critical delegation."}
        ]
        dashboard["ai_dashboard_release_readiness_center"]["release_status"] = "blocked"
        dashboard["ai_dashboard_release_readiness_center"]["blocking_checks"] = [
            {"title": "Release blocked", "status": "blocked", "summary": "Release cannot proceed."}
        ]
        dashboard["ai_runtime_policy_linter"]["linter_status"] = "critical"
        dashboard["ai_runtime_policy_linter"]["critical_issues"] = [
            {"issue": "Policy conflict", "severity": "critical", "recommendation": "Manual review."}
        ]
        dashboard["ai_runtime_capability_governance"]["forbidden_capabilities"] = [
            {"title": "Forbidden capability", "risk_level": "critical", "summary": "Forbidden."}
        ]
        return dashboard

    def test_build_weekly_executive_report_returns_dict(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertIsInstance(report, dict)
        self.assertIn("report_status", report)

    def test_headline_is_not_empty_and_short(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertTrue(report["headline"])
        self.assertLessEqual(len(report["headline"]), 80)

    def test_executive_summary_is_not_empty_and_short(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertTrue(report["executive_summary"])
        self.assertLessEqual(len(report["executive_summary"]), 150)

    def test_weekly_health_is_dict(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertIsInstance(report["weekly_health"], dict)

    def test_top_risks_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        self.assertIsInstance(report["top_risks"], list)

    def test_governance_review_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        self.assertIsInstance(report["governance_review"], list)

    def test_ops_review_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertIsInstance(report["ops_review"], list)

    def test_release_review_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertIsInstance(report["release_review"], list)

    def test_export_review_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertIsInstance(report["export_review"], list)

    def test_capability_review_is_list(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        self.assertIsInstance(report["capability_review"], list)

    def test_next_week_priorities_is_list_and_limited(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        self.assertIsInstance(report["next_week_priorities"], list)
        self.assertLessEqual(len(report["next_week_priorities"]), 5)

    def test_critical_status_is_resolved(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        self.assertEqual(report["report_status"], "critical")

    def test_attention_status_is_resolved(self):
        dashboard = self._base_dashboard()
        dashboard["ai_runtime_daily_operator_brief"]["brief_status"] = "attention"
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(dashboard)
        self.assertEqual(report["report_status"], "attention")

    def test_stable_status_is_resolved(self):
        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._base_dashboard())
        self.assertEqual(report["report_status"], "stable")

    def test_runtime_weekly_executive_report_export_route_registered(self):
        from web_ui.app import app

        report = AIRuntimeWeeklyExecutiveReportService.build_weekly_executive_report(self._critical_dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-weekly-executive-report-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_weekly_executive_report": report}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-weekly-executive-report-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-weekly-executive-report-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-weekly-executive-report-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime OS 每周高管报告".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("分类".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 每周高管报告".encode("utf-8"), md_response.data)

    def test_ai_dashboard_page_keeps_weekly_executive_report_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime OS 每周高管报告", template)
        self.assertIn("/ai-dashboard/runtime-weekly-executive-report-export?format=txt", template)

    def test_no_automatic_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_weekly_executive_report_service.py").read_text(encoding="utf-8")
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
