import unittest

from services.ai_dashboard_module_search_service import AIDashboardModuleSearchService


class AIDashboardModuleSearchServiceTest(unittest.TestCase):
    def test_build_module_search_center_returns_dict(self):
        center = AIDashboardModuleSearchService.build_module_search_center()
        self.assertIsInstance(center, dict)
        self.assertIn("search_status", center)
        self.assertIn("search_entry", center)
        self.assertIn("search_index", center)
        self.assertIn("module_keywords", center)
        self.assertIn("runtime_modules", center)
        self.assertIn("export_modules", center)
        self.assertIn("ops_modules", center)
        self.assertIn("governance_modules", center)
        self.assertIn("documentation_modules", center)
        self.assertIn("navigation_modules", center)
        self.assertIn("missing_search_targets", center)
        self.assertIn("results", center)
        self.assertIn("suggested_keywords", center)
        self.assertIn("quick_filters", center)

    def test_search_index_is_not_empty(self):
        center = AIDashboardModuleSearchService.build_module_search_center()
        self.assertTrue(center["search_index"])

    def test_empty_query_returns_recommended_results(self):
        center = AIDashboardModuleSearchService.build_module_search_center()
        self.assertEqual(center["search_status"], "normal")
        self.assertTrue(center["results"])

    def test_search_runtime_has_results(self):
        center = AIDashboardModuleSearchService.build_module_search_center("Runtime")
        self.assertEqual(center["search_status"], "normal")
        self.assertTrue(center["results"])

    def test_search_export_chinese_has_results(self):
        center = AIDashboardModuleSearchService.build_module_search_center("导出")
        self.assertEqual(center["search_status"], "normal")
        self.assertTrue(center["results"])

    def test_no_match_returns_no_match(self):
        center = AIDashboardModuleSearchService.build_module_search_center("zzzz_not_existing_dashboard_module_987654")
        self.assertEqual(center["search_status"], "attention")
        self.assertEqual(center["results"], [])

    def test_markdown_export_contains_title(self):
        markdown = AIDashboardModuleSearchService.build_module_search_markdown(
            AIDashboardModuleSearchService.build_module_search_center("Runtime")
        )
        self.assertIn("# AI Dashboard 模块搜索中心", markdown)
        self.assertIn("## 搜索结果", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/module-search", rules)
        self.assertIn("/ai-dashboard/module-search-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            response = client.get("/ai-dashboard/module-search?q=Runtime")
            txt_response = client.get("/ai-dashboard/module-search-export?format=txt&q=Runtime")
            csv_response = client.get("/ai-dashboard/module-search-export?format=csv&q=Runtime")
            md_response = client.get("/ai-dashboard/module-search-export?format=md&q=Runtime")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 模块搜索中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)

    def test_dashboard_template_contains_module_search_center_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 模块搜索中心", template)
        self.assertIn("搜索模块", template)
        self.assertIn("查看模块搜索详情", template)
        self.assertIn("Runtime", template)
        self.assertIn("导出", template)
        self.assertIn("文档", template)

    def test_module_search_page_template_title_exists(self):
        with open("web_ui/templates/ai_dashboard_module_search.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 模块搜索中心", template)


if __name__ == "__main__":
    unittest.main()
