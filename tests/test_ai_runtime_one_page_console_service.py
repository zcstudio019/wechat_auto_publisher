import unittest
from unittest.mock import patch

from services.ai_runtime_one_page_console_service import AIRuntimeOnePageConsoleService


class AIRuntimeOnePageConsoleServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_entry_router": {
                "router_status": "normal",
                "summary": "router normal",
                "primary_entry": {
                    "title": "AI Dashboard 管理首页中心",
                    "route": "/ai-dashboard/home",
                    "reason": "normal entry",
                    "priority": "normal",
                },
            },
            "ai_runtime_practical_console": {
                "console_status": "normal",
                "summary": "practical normal",
                "must_handle_today": [{"title": f"must {index}", "priority": "high"} for index in range(6)],
                "observe_today": [{"title": f"watch {index}", "priority": "medium"} for index in range(6)],
                "never_automate": [{"title": f"never {index}", "priority": "critical"} for index in range(6)],
                "weekly_improvement_focus": [{"title": f"focus {index}", "priority": "medium"} for index in range(6)],
            },
            "ai_runtime_executive_digest_center": {"digest_status": "stable", "one_line_summary": "stable"},
            "ai_runtime_os_kernel": {"kernel_status": "healthy", "summary": "kernel ok"},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy", "summary": "ops ok"},
            "ai_dashboard_release_readiness_center": {"release_status": "ready", "summary": "release ok"},
            "ai_runtime_integrity_center": {"integrity_status": "stable", "integrity_score": 95},
            "ai_runtime_immune_center": {"immune_status": "stable"},
            "ai_runtime_resilience_center": {"resilience_status": "resilient"},
        }

    def test_build_one_page_console_returns_dict(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertIsInstance(console, dict)
        self.assertIn("console_status", console)

    def test_headline_not_empty_and_lte_80(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertTrue(console["headline"])
        self.assertLessEqual(len(console["headline"]), 80)

    def test_primary_entry_is_not_empty(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertTrue(console["primary_entry"])
        self.assertTrue(console["primary_entry"]["route"])

    def test_today_must_do_is_list_and_lte_5(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertIsInstance(console["today_must_do"], list)
        self.assertLessEqual(len(console["today_must_do"]), 5)

    def test_today_watch_is_list_and_lte_5(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertIsInstance(console["today_watch"], list)
        self.assertLessEqual(len(console["today_watch"]), 5)

    def test_never_do_is_list_and_lte_5(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertIsInstance(console["never_do"], list)
        self.assertLessEqual(len(console["never_do"]), 5)

    def test_system_health_is_not_empty(self):
        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        self.assertTrue(console["system_health"])

    def test_runtime_one_page_console_export_route_registered(self):
        from web_ui.app import app

        console = AIRuntimeOnePageConsoleService.build_one_page_console(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-one-page-console-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_one_page_console": console}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-one-page-console-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-one-page-console-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-one-page-console-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime OS 单页总控台】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("分类".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 单页总控台".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_one_page_console_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime OS 单页总控台", template)


if __name__ == "__main__":
    unittest.main()
