import unittest
from unittest.mock import patch

from services.ai_runtime_entry_router_service import AIRuntimeEntryRouterService


class AIRuntimeEntryRouterServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_practical_console": {"console_status": "normal"},
            "ai_dashboard_release_readiness_center": {"release_status": "ready"},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
            "ai_runtime_mission_control_center": {"mission_status": "normal"},
            "ai_runtime_signal_intelligence": {"signal_status": "stable"},
            "ai_runtime_os_kernel": {"kernel_status": "healthy"},
            "ai_dashboard_navigation_center": {"navigation_status": "normal"},
            "ai_dashboard_documentation_center": {"documentation_status": "normal"},
            "ai_dashboard_module_search_center": {"module_search_status": "normal"},
        }

    def test_build_entry_router_returns_dict(self):
        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        self.assertIsInstance(router, dict)
        self.assertIn("router_status", router)

    def test_primary_entry_is_not_empty(self):
        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        self.assertTrue(router["primary_entry"])
        self.assertTrue(router["primary_entry"]["route"])

    def test_role_based_entries_is_not_empty(self):
        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        self.assertTrue(router["role_based_entries"])

    def test_quick_routes_is_not_empty(self):
        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        self.assertTrue(router["quick_routes"])
        self.assertLessEqual(len(router["quick_routes"]), 12)

    def test_urgent_can_route_to_release_ops_or_mission(self):
        release_dashboard = self._dashboard()
        release_dashboard["ai_dashboard_release_readiness_center"] = {"release_status": "blocked"}
        self.assertEqual(
            AIRuntimeEntryRouterService.build_entry_router(release_dashboard)["primary_entry"]["route"],
            "/ai-dashboard/release-readiness",
        )

        ops_dashboard = self._dashboard()
        ops_dashboard["ai_dashboard_ops_health_center"] = {"ops_status": "critical"}
        self.assertEqual(
            AIRuntimeEntryRouterService.build_entry_router(ops_dashboard)["primary_entry"]["route"],
            "/ai-dashboard/ops-health",
        )

        mission_dashboard = self._dashboard()
        mission_dashboard["ai_runtime_mission_control_center"] = {"mission_status": "critical"}
        self.assertEqual(
            AIRuntimeEntryRouterService.build_entry_router(mission_dashboard)["primary_entry"]["route"],
            "/ai-dashboard/mission-control",
        )

    def test_normal_routes_to_home(self):
        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        self.assertEqual(router["primary_entry"]["route"], "/ai-dashboard/home")
        self.assertEqual(router["router_status"], "normal")

    def test_runtime_entry_router_export_route_registered(self):
        from web_ui.app import app

        router = AIRuntimeEntryRouterService.build_entry_router(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-entry-router-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_entry_router": router}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-entry-router-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-entry-router-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-entry-router-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime OS 入口路由器】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("入口".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 入口路由器".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_entry_router_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime OS 入口路由器", template)


if __name__ == "__main__":
    unittest.main()
