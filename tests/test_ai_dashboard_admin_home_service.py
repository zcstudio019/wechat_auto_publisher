import unittest
from unittest.mock import patch

from services.ai_dashboard_admin_home_service import AIDashboardAdminHomeService


class AIDashboardAdminHomeServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_runtime_executive_dashboard": {
                "executive_status": "stable",
                "executive_summary": "executive ok",
            },
            "ai_runtime_observability_center": {
                "runtime_status": "healthy",
                "runtime_health": {"summary": "runtime ok"},
            },
            "ai_runtime_alert_center": {"alert_status": "normal"},
            "ai_runtime_incident_center": {"incident_status": "none"},
            "ai_runtime_weekly_review_center": {"weekly_status": "normal", "summary": "weekly ok"},
            "ai_runtime_trust_center": {"trust_status": "normal", "trust_summary": "trust ok"},
            "ai_runtime_boundary_center": {"boundary_status": "normal", "boundary_summary": "boundary ok"},
            "ai_runtime_constitution_center": {"constitution_status": "normal", "constitution_summary": "constitution ok"},
            "ai_dashboard_ops_health_center": {
                "ops_status": "healthy",
                "summary": "ops ok",
                "smoke_test_status": {"status": "passed", "summary": "smoke ok"},
                "runtime_status": {"status": "ok", "summary": "runtime key ok"},
                "route_status": {"status": "ok", "summary": "route ok"},
                "template_status": {"status": "ok", "summary": "template ok"},
            },
            "ai_dashboard_export_operations_center": {"operations_status": "normal", "summary": "export ok"},
            "ai_dashboard_ops_maintenance_center": {"maintenance_status": "normal", "summary": "maintenance ok"},
            "ai_dashboard_documentation_center": {"documentation_status": "normal"},
            "ai_dashboard_navigation_center": {
                "recommended_paths": [
                    {"name": "导航路径", "steps": ["Navigation", "Documentation"], "summary": "ok"}
                ]
            },
        }

    def test_build_admin_home_center_returns_dict(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("admin_home_status", center)
        self.assertIn("home_status", center)
        self.assertIn("quick_entry_groups", center)
        self.assertIn("priority_modules", center)
        self.assertIn("runtime_overview", center)
        self.assertIn("system_shortcuts", center)

    def test_today_overview_is_not_empty(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        self.assertTrue(center["today_overview"])

    def test_quick_entries_include_navigation_docs_architecture_and_ops(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        titles = {item["title"] for item in center["quick_entries"]}
        self.assertIn("导航中心", titles)
        self.assertIn("文档中心", titles)
        self.assertIn("架构地图", titles)
        self.assertIn("运维健康", titles)

    def test_runtime_and_ops_entries_are_not_empty(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        self.assertTrue(center["runtime_entries"])
        self.assertTrue(center["ops_entries"])

    def test_recommended_paths_are_not_empty(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_paths"])

    def test_status_attention_and_critical(self):
        warning_dashboard = self._dashboard_fixture()
        warning_dashboard["ai_dashboard_ops_health_center"]["ops_status"] = "warning"
        self.assertEqual(AIDashboardAdminHomeService.build_admin_home_center(warning_dashboard)["admin_home_status"], "attention")

        critical_dashboard = self._dashboard_fixture()
        critical_dashboard["ai_runtime_incident_center"]["incident_status"] = "critical"
        self.assertEqual(AIDashboardAdminHomeService.build_admin_home_center(critical_dashboard)["admin_home_status"], "critical")

    def test_markdown_export_contains_title(self):
        center = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        markdown = AIDashboardAdminHomeService.build_admin_home_markdown(center)
        self.assertIn("# AI Dashboard 管理首页中心", markdown)
        self.assertIn("## 今日总览", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/admin-home", rules)
        self.assertIn("/ai-dashboard/admin-home-export", rules)
        self.assertIn("/ai-dashboard/home", rules)
        self.assertIn("/ai-dashboard/home-export", rules)

        fixture = AIDashboardAdminHomeService.build_admin_home_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={}):
            with patch("web_ui.app.AIDashboardAdminHomeService.build_admin_home_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/admin-home")
                    txt_response = client.get("/ai-dashboard/admin-home-export?format=txt")
                    csv_response = client.get("/ai-dashboard/admin-home-export?format=csv")
                    md_response = client.get("/ai-dashboard/home-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 管理首页中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
