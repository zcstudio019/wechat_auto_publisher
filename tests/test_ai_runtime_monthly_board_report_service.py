import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_monthly_board_report_service import AIRuntimeMonthlyBoardReportService


class AIRuntimeMonthlyBoardReportServiceTest(unittest.TestCase):
    def _base_dashboard(self):
        return {
            "ai_runtime_weekly_executive_report": {
                "report_status": "stable",
                "weekly_health": {
                    "runtime": "stable",
                    "governance": "stable",
                    "ops": "healthy",
                    "release": "ready",
                    "capability": "stable",
                },
                "wins_this_week": [
                    {"title": "Ops Health healthy", "status": "healthy", "source": "Weekly", "suggestion": "Keep watching."}
                ],
                "top_risks": [],
            },
            "ai_runtime_governance_summary": {
                "summary_status": "stable",
                "delegation_risks": [],
                "high_risk_capabilities": [],
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
                    {"title": "Release readiness passed", "status": "passed", "summary": "Release checks passed."}
                ],
            },
            "ai_dashboard_export_operations_center": {
                "operations_status": "normal",
                "warnings": [],
                "failed_items": [],
            },
            "ai_dashboard_ops_maintenance_center": {
                "today_tasks": [],
                "recommended_actions": [],
            },
            "ai_runtime_policy_compiler": {
                "policy_conflicts": [],
                "warning_policies": [],
            },
            "ai_runtime_policy_linter": {
                "linter_status": "clean",
                "critical_issues": [],
                "warning_issues": [],
            },
            "ai_runtime_capability_governance": {
                "governance_status": "stable",
                "forbidden_capabilities": [],
                "delegation_risks": [],
                "approval_required_capabilities": [],
            },
            "ai_dashboard_release_package_center": {
                "package_items": [],
                "recommended_actions": [],
            },
            "ai_dashboard_release_runbook_center": {
                "runbook_steps": [],
                "recommended_actions": [],
            },
            "ai_runtime_strategy_center": {
                "technical_debt_risks": [],
            },
        }

    def _critical_dashboard(self):
        dashboard = self._base_dashboard()
        dashboard["ai_runtime_weekly_executive_report"]["report_status"] = "critical"
        dashboard["ai_runtime_weekly_executive_report"]["top_risks"] = [
            {"title": "Runtime governance threat", "status": "critical", "risk": "critical", "source": "Weekly", "suggestion": "Board review."}
        ]
        dashboard["ai_runtime_governance_summary"]["summary_status"] = "critical"
        dashboard["ai_runtime_governance_summary"]["delegation_risks"] = [
            {"title": "High delegation risk", "risk_level": "critical", "summary": "Delegation needs governance."}
        ]
        dashboard["ai_dashboard_release_readiness_center"]["release_status"] = "blocked"
        dashboard["ai_dashboard_release_readiness_center"]["blocking_checks"] = [
            {"title": "Release blocked", "status": "blocked", "summary": "Release cannot proceed."}
        ]
        dashboard["ai_runtime_capability_governance"]["forbidden_capabilities"] = [
            {"title": "Forbidden capability", "risk_level": "critical", "summary": "Forbidden."}
        ]
        dashboard["ai_runtime_capability_governance"]["delegation_risks"] = [
            {"title": "Delegation risk", "risk_level": "critical", "summary": "Critical."}
        ]
        return dashboard

    def test_build_monthly_board_report_returns_dict(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertIsInstance(report, dict)
        self.assertIn("board_status", report)

    def test_board_status_is_resolved(self):
        self.assertEqual(
            AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())["board_status"],
            "healthy",
        )
        attention = self._base_dashboard()
        attention["ai_runtime_governance_summary"]["summary_status"] = "attention"
        self.assertEqual(
            AIRuntimeMonthlyBoardReportService.build_monthly_board_report(attention)["board_status"],
            "attention",
        )
        self.assertEqual(
            AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._critical_dashboard())["board_status"],
            "critical",
        )

    def test_headline_is_short(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertTrue(report["headline"])
        self.assertLessEqual(len(report["headline"]), 80)

    def test_board_summary_is_short(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertTrue(report["board_summary"])
        self.assertLessEqual(len(report["board_summary"]), 200)

    def test_monthly_trends_is_dict(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertIsInstance(report["monthly_trends"], dict)

    def test_major_achievements_is_list(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertIsInstance(report["major_achievements"], list)

    def test_strategic_threats_is_list(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._critical_dashboard())
        self.assertIsInstance(report["strategic_threats"], list)

    def test_quarter_focus_is_limited(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._critical_dashboard())
        self.assertIsInstance(report["quarter_focus"], list)
        self.assertLessEqual(len(report["quarter_focus"]), 5)

    def test_investment_priorities_is_limited(self):
        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._base_dashboard())
        self.assertIsInstance(report["investment_priorities"], list)
        self.assertLessEqual(len(report["investment_priorities"]), 5)

    def test_runtime_monthly_board_report_export_route_registered(self):
        from web_ui.app import app

        report = AIRuntimeMonthlyBoardReportService.build_monthly_board_report(self._critical_dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-monthly-board-report-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_monthly_board_report": report}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-monthly-board-report-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-monthly-board-report-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-monthly-board-report-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime OS 月度董事会报告".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("分类".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 月度董事会报告".encode("utf-8"), md_response.data)

    def test_ai_dashboard_page_keeps_monthly_board_report_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime OS 月度董事会报告", template)
        self.assertIn("/ai-dashboard/runtime-monthly-board-report-export?format=txt", template)

    def test_no_automatic_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_monthly_board_report_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def apply",
            "def run",
            "subprocess",
            "publish_approved_articles",
            "scheduler",
            "worker",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
