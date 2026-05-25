import unittest
from unittest.mock import patch

from services.ai_dashboard_documentation_service import AIDashboardDocumentationService


class AIDashboardDocumentationServiceTest(unittest.TestCase):
    def test_build_documentation_center_returns_dict(self):
        center = AIDashboardDocumentationService.build_documentation_center()
        self.assertIsInstance(center, dict)
        self.assertIn("documentation_status", center)
        self.assertIn("module_catalog", center)
        self.assertIn("module_docs", center)
        self.assertIn("runtime_docs", center)
        self.assertIn("ops_docs", center)
        self.assertIn("data_file_docs", center)
        self.assertIn("usage_guides", center)

    def test_module_catalog_covers_runtime_key_modules(self):
        center = AIDashboardDocumentationService.build_documentation_center()
        modules = {item["module_name"] for item in center["module_catalog"]}
        required = {
            "Runtime Observability",
            "Runtime Alert",
            "Runtime Recovery",
            "Runtime Incident",
            "Runtime Postmortem",
            "Runtime Learning",
            "Runtime Knowledge Sync",
            "Runtime Weekly Review",
            "Runtime Feedback Loop",
            "Runtime Evolution",
            "Runtime Orchestrator",
            "Runtime Control Policy",
            "Runtime Policy Gate",
            "Runtime Confidence",
            "Runtime Trust",
            "Runtime Delegation Readiness",
            "Runtime Boundary",
            "Runtime Constitution",
            "Runtime Snapshot",
            "Runtime Snapshot Diff",
            "Runtime Timeline",
            "Runtime Forecast",
            "Runtime Predictive Action",
            "Runtime Continuous Improvement",
            "Runtime Executive Dashboard",
            "Export Operations",
            "Ops Health",
            "Ops Maintenance",
            "Architecture Map",
            "Smoke Test",
        }
        self.assertTrue(required.issubset(modules))

    def test_readonly_matrix_contains_affects_review_publish(self):
        center = AIDashboardDocumentationService.build_documentation_center()
        self.assertTrue(center["readonly_matrix"])
        self.assertTrue(all("affects_review_publish" in item for item in center["readonly_matrix"]))
        self.assertTrue(all(item["affects_review_publish"] is False for item in center["readonly_matrix"]))

    def test_route_and_export_docs_are_not_empty(self):
        center = AIDashboardDocumentationService.build_documentation_center()
        self.assertTrue(center["route_docs"])
        self.assertTrue(center["export_docs"])

    def test_standard_documentation_sections_are_built(self):
        center = AIDashboardDocumentationService.build_documentation_center()
        self.assertTrue(center["module_docs"])
        self.assertTrue(center["runtime_docs"])
        self.assertTrue(center["ops_docs"])
        self.assertTrue(center["architecture_docs"])
        self.assertTrue(center["route_docs"])
        self.assertTrue(center["data_file_docs"])
        self.assertTrue(center["usage_guides"])
        self.assertTrue(center["recommended_actions"])

    def test_markdown_export_contains_title(self):
        markdown = AIDashboardDocumentationService.build_documentation_markdown()
        self.assertIn("# AI Dashboard 文档中心", markdown)
        self.assertIn("## 模块清单", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/documentation", rules)
        self.assertIn("/ai-dashboard/documentation-export", rules)

        fixture = {
            "documentation_status": "normal",
            "summary": "ok",
            "module_docs": [],
            "runtime_docs": [],
            "export_docs": [],
            "ops_docs": [],
            "architecture_docs": [],
            "maintenance_docs": [],
            "route_docs": [],
            "data_file_docs": [],
            "usage_guides": [],
            "recommended_actions": [],
            "module_catalog": [],
            "layer_docs": [],
            "service_docs": [],
            "test_docs": [],
            "readonly_matrix": [],
            "maintenance_notes": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardDocumentationService.build_documentation_center", return_value=fixture):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/documentation")
                txt_response = client.get("/ai-dashboard/documentation-export?format=txt")
                csv_response = client.get("/ai-dashboard/documentation-export?format=csv")
                md_response = client.get("/ai-dashboard/documentation-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 文档中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
