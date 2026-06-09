import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_daily_operator_brief_service import AIRuntimeDailyOperatorBriefService


class AIRuntimeDailyOperatorBriefServiceTest(unittest.TestCase):
    def _base_dashboard(self):
        return {
            "ai_runtime_one_page_console": {
                "console_status": "normal",
                "primary_entry": {
                    "title": "AI Dashboard 管理首页中心",
                    "route": "/ai-dashboard/home",
                    "reason": "normal entry",
                },
            },
            "ai_runtime_practical_console": {
                "console_status": "normal",
                "must_handle_today": [],
                "observe_today": [],
                "never_automate": [
                    {"title": "不要自动发布", "priority": "critical", "summary": "发布必须人工。"}
                ],
            },
            "ai_runtime_governance_summary": {
                "summary_status": "stable",
                "high_risk_capabilities": [],
                "human_only_capabilities": [],
                "forbidden_capabilities": [],
                "delegation_risks": [],
            },
            "ai_dashboard_release_readiness_center": {
                "release_status": "ready",
                "must_fix_before_release": [],
                "warning_checks": [],
            },
            "ai_dashboard_ops_health_center": {
                "ops_status": "healthy",
                "risk_items": [],
                "warning_items": [],
            },
            "ai_runtime_policy_linter": {
                "linter_status": "clean",
                "critical_issues": [],
                "warning_issues": [],
                "human_review_gaps": [],
            },
            "ai_runtime_command_layer": {
                "blocked_commands": [],
                "human_review_commands": [],
            },
            "ai_runtime_capability_governance": {
                "forbidden_capabilities": [],
                "approval_required_capabilities": [],
                "delegation_risks": [],
            },
            "ai_runtime_mission_control_center": {
                "mission_status": "normal",
                "critical_missions": [],
            },
            "ai_runtime_entry_router": {
                "primary_entry": {
                    "title": "AI Dashboard 管理首页中心",
                    "route": "/ai-dashboard/home",
                    "reason": "normal entry",
                }
            },
            "ai_runtime_signal_intelligence": {"warning_signals": []},
            "ai_runtime_forecast_center": {"potential_risks": []},
            "ai_runtime_policy_compiler": {
                "blocked_policies": [],
                "human_only_policies": [],
                "policy_conflicts": [],
            },
            "ai_runtime_judgment_center": {"dangerous_automations": []},
            "ai_runtime_governance_court_center": {"forbidden_domains": []},
            "ai_runtime_integrity_center": {"governance_conflicts": []},
            "ai_runtime_immune_center": {"governance_corruption_risks": []},
        }

    def _urgent_dashboard(self):
        dashboard = self._base_dashboard()
        dashboard["ai_runtime_governance_summary"] = {
            "summary_status": "critical",
            "high_risk_capabilities": [
                {"title": "High risk capability", "risk_level": "critical", "summary": "Needs review."}
            ],
            "human_only_capabilities": [
                {"title": "Human only capability", "risk_level": "critical", "summary": "Manual only."}
            ],
            "forbidden_capabilities": [
                {"title": "Forbidden capability", "risk_level": "critical", "summary": "Never automate."}
            ],
            "delegation_risks": [
                {"title": "Delegation risk", "risk_level": "critical", "summary": "Critical delegation risk."}
            ],
        }
        dashboard["ai_runtime_command_layer"]["blocked_commands"] = [
            {"title": "Review high risk automation", "risk_level": "critical", "recommended_route": "/ai-dashboard"}
        ]
        dashboard["ai_runtime_command_layer"]["human_review_commands"] = [
            {"title": "Review high risk automation", "risk_level": "critical", "recommended_route": "/ai-dashboard"}
        ]
        dashboard["ai_runtime_policy_linter"]["critical_issues"] = [
            {"issue": "Forbidden automation", "severity": "critical", "recommendation": "Manual review."}
        ]
        dashboard["ai_runtime_capability_governance"]["forbidden_capabilities"] = [
            {"title": "Forbidden capability", "risk_level": "critical", "summary": "Never automate."}
        ]
        dashboard["ai_runtime_capability_governance"]["delegation_risks"] = [
            {"title": "Delegation risk", "risk_level": "critical", "summary": "Critical delegation risk."}
        ]
        dashboard["ai_dashboard_release_readiness_center"]["must_fix_before_release"] = [
            {"name": "Smoke Test fail", "status": "blocked", "summary": "Fix smoke test."}
        ]
        return dashboard

    def test_build_daily_operator_brief_returns_dict(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertIsInstance(brief, dict)
        self.assertIn("brief_status", brief)

    def test_headline_is_not_empty_and_short(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertTrue(brief["headline"])
        self.assertLessEqual(len(brief["headline"]), 80)

    def test_brief_summary_is_not_empty_and_short(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertTrue(brief["brief_summary"])
        self.assertLessEqual(len(brief["brief_summary"]), 120)

    def test_must_do_today_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._urgent_dashboard())
        self.assertIsInstance(brief["must_do_today"], list)

    def test_watch_today_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertIsInstance(brief["watch_today"], list)

    def test_never_do_today_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertIsInstance(brief["never_do_today"], list)

    def test_human_review_today_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._urgent_dashboard())
        self.assertIsInstance(brief["human_review_today"], list)

    def test_governance_risks_today_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._urgent_dashboard())
        self.assertIsInstance(brief["governance_risks_today"], list)

    def test_recommended_pages_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertIsInstance(brief["recommended_pages"], list)
        routes = {item["route"] for item in brief["recommended_pages"]}
        self.assertIn("/ai-dashboard/home", routes)
        self.assertIn("/ai-dashboard/mission-control", routes)
        self.assertIn("/ai-dashboard/ops-health", routes)
        self.assertIn("/ai-dashboard/release-readiness", routes)

    def test_recommended_exports_is_list(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertIsInstance(brief["recommended_exports"], list)
        self.assertTrue(brief["recommended_exports"])

    def test_urgent_status_is_resolved(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._urgent_dashboard())
        self.assertEqual(brief["brief_status"], "urgent")

    def test_attention_status_is_resolved(self):
        dashboard = self._base_dashboard()
        dashboard["ai_runtime_governance_summary"]["summary_status"] = "attention"
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(dashboard)
        self.assertEqual(brief["brief_status"], "attention")

    def test_normal_status_is_resolved(self):
        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._base_dashboard())
        self.assertEqual(brief["brief_status"], "normal")

    def test_runtime_daily_operator_brief_export_route_registered(self):
        from web_ui.app import app

        brief = AIRuntimeDailyOperatorBriefService.build_daily_operator_brief(self._urgent_dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-daily-operator-brief-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_daily_operator_brief": brief}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-daily-operator-brief-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-daily-operator-brief-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-daily-operator-brief-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime OS 每日操作简报".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("分类".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 每日操作简报".encode("utf-8"), md_response.data)

    def test_ai_dashboard_page_keeps_daily_operator_brief_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime OS 每日操作简报", template)
        self.assertIn("/ai-dashboard/runtime-daily-operator-brief-export?format=txt", template)

    def test_no_automatic_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_daily_operator_brief_service.py").read_text(encoding="utf-8")
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
