import unittest
from unittest.mock import patch

from services.ai_dashboard_ux_declutter_service import AIDashboardUXDeclutterService


class AIDashboardUXDeclutterServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_dashboard_navigation_index_center": {
                "quick_links": [
                    {"title": "AI Dashboard 管理首页中心", "status": "normal", "summary": "管理入口"}
                ],
                "missing_links": [
                    {"title": "缺失详情入口", "suggestion": "补充详情链接"}
                ],
            }
        }

    def test_build_center_returns_required_fields(self):
        center = AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center(self._dashboard_fixture())
        for key in [
            "ux_status",
            "summary",
            "current_entry_map",
            "recommended_entry_order",
            "high_frequency_entries",
            "low_frequency_entries",
            "hidden_or_collapsed_candidates",
            "top_priority_cards",
            "secondary_cards",
            "deep_dive_cards",
            "duplicate_entries",
            "overloaded_sections",
            "navigation_friction_points",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_center_contains_declutter_title(self):
        center = AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center({})
        titles = [item.get("title") for item in center["recommended_entry_order"]]
        self.assertIn("AI Dashboard 体验减负与入口重排", titles)
        self.assertTrue(center["recommended_actions"])

    def test_text_and_rows_exports_contain_data(self):
        center = AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center({})
        text = AIDashboardUXDeclutterService.build_ux_declutter_text(center)
        rows = AIDashboardUXDeclutterService.build_ux_declutter_rows(center)
        self.assertIn("【AI Dashboard 体验减负与入口重排】", text)
        self.assertTrue(rows)
        self.assertIn("分类", rows[0])

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/ux-declutter", rules)
        self.assertIn("/ai-dashboard/ux-declutter-export", rules)

        fixture = AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center({})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={}):
            with patch(
                "web_ui.app.AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center",
                return_value=fixture,
            ):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/ux-declutter")
                    txt_response = client.get("/ai-dashboard/ux-declutter-export?format=txt")
                    csv_response = client.get("/ai-dashboard/ux-declutter-export?format=csv")
                    md_response = client.get("/ai-dashboard/ux-declutter-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 体验减负与入口重排".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
