import unittest
from unittest.mock import patch

from services.ai_dashboard_navigation_service import AIDashboardNavigationService
from services.ai_dashboard_navigation_index_service import AIDashboardNavigationIndexService


class AIDashboardNavigationServiceTest(unittest.TestCase):
    def test_build_navigation_center_returns_dict(self):
        center = AIDashboardNavigationService.build_navigation_center()
        self.assertIsInstance(center, dict)
        self.assertIn("navigation_status", center)
        self.assertIn("quick_links", center)
        self.assertIn("section_index", center)
        self.assertIn("runtime_index", center)
        self.assertIn("export_index", center)
        self.assertIn("ops_index", center)
        self.assertIn("architecture_index", center)
        self.assertIn("documentation_index", center)
        self.assertIn("missing_links", center)
        self.assertIn("broken_routes", center)
        self.assertIn("category_navigation", center)
        self.assertIn("module_index", center)
        self.assertIn("page_navigation", center)
        self.assertIn("export_navigation", center)
        self.assertIn("route_navigation", center)
        self.assertIn("dashboard_key_navigation", center)

    def test_category_navigation_correct(self):
        center = AIDashboardNavigationService.build_navigation_center()
        categories = {item["category"] for item in center["category_navigation"]}
        required = {
            "Executive",
            "Runtime",
            "Forecast",
            "Trust & Boundary",
            "Governance",
            "Ops",
            "Export",
            "Architecture",
            "Documentation",
        }
        self.assertTrue(required.issubset(categories))

    def test_navigation_index_wrapper_returns_standard_fields(self):
        center = AIDashboardNavigationIndexService.build_navigation_index_center()
        self.assertIn("quick_links", center)
        self.assertIn("runtime_index", center)
        self.assertIn("recommended_actions", center)

    def test_module_export_route_and_dashboard_key_indexes_are_not_empty(self):
        center = AIDashboardNavigationService.build_navigation_center()
        self.assertTrue(center["module_index"])
        self.assertTrue(center["export_navigation"])
        self.assertTrue(center["route_navigation"])
        self.assertTrue(center["dashboard_key_navigation"])

    def test_markdown_export_contains_title(self):
        markdown = AIDashboardNavigationService.build_navigation_markdown()
        self.assertIn("# AI Dashboard 导航与索引中心", markdown)
        self.assertIn("## 分类导航", markdown)

    def test_navigation_rows_use_required_csv_fields(self):
        rows = AIDashboardNavigationService.build_navigation_rows()
        self.assertTrue(rows)
        for field in ["分类", "标题", "路径/锚点", "状态", "说明", "建议"]:
            self.assertIn(field, rows[0])

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/navigation-index", rules)
        self.assertIn("/ai-dashboard/navigation-index-export", rules)

        fixture = {
            "navigation_status": "normal",
            "summary": "ok",
            "quick_links": [{"type": "quick_link", "title": "AI Dashboard 导航与索引中心", "path": "/ai-dashboard/navigation-index", "status": "normal", "summary": "ok", "suggestion": "ok"}],
            "section_index": [],
            "runtime_index": [],
            "export_index": [],
            "ops_index": [],
            "architecture_index": [],
            "documentation_index": [],
            "missing_links": [],
            "broken_routes": [],
            "category_navigation": [{"category": "Executive", "modules": ["Runtime Executive Dashboard"], "summary": "ok"}],
            "module_index": [
                {
                    "module_name": "Navigation Center",
                    "chinese_name": "AI Dashboard 导航与索引中心",
                    "dashboard_key": "ai_dashboard_navigation_index_center",
                    "route": "/ai-dashboard/navigation-index",
                    "export_route": "/ai-dashboard/navigation-index-export",
                    "layer": "Documentation Layer",
                    "category": "Documentation",
                    "readonly": True,
                    "service_file": "services/ai_dashboard_navigation_service.py",
                    "summary": "ok",
                }
            ],
            "page_navigation": [{"title": "AI Dashboard 导航与索引中心", "route": "/ai-dashboard/navigation-index", "purpose": "ok"}],
            "export_navigation": [{"module": "Navigation Center", "export_route": "/ai-dashboard/navigation-index-export", "formats": ["txt", "csv"], "summary": "ok"}],
            "service_navigation": [{"service_file": "services/ai_dashboard_navigation_service.py", "responsibility": "ok", "related_modules": ["Navigation Center"]}],
            "route_navigation": [{"route": "/ai-dashboard/navigation-index", "method": "GET", "summary": "ok"}],
            "dashboard_key_navigation": [{"dashboard_key": "ai_dashboard_navigation_index_center", "module": "Navigation Center", "summary": "ok"}],
            "recommended_paths": [{"name": "新手查看路径", "steps": ["Executive Dashboard", "Navigation"], "summary": "ok"}],
            "quick_actions": [{"label": "查看 Navigation Center", "route": "/ai-dashboard/navigation", "summary": "ok"}],
            "recommended_actions": ["保持导航中心严格只读"],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardNavigationIndexService.build_navigation_index_center", return_value=fixture):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/navigation-index")
                txt_response = client.get("/ai-dashboard/navigation-index-export?format=txt")
                csv_response = client.get("/ai-dashboard/navigation-index-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 导航与索引中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
