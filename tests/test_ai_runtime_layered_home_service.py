import unittest
from unittest.mock import patch

from services.ai_runtime_layered_home_service import AIRuntimeLayeredHomeService


class AIRuntimeLayeredHomeServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_practical_console": {"console_status": "normal"},
            "ai_dashboard_release_readiness_center": {"release_status": "ready"},
            "ai_runtime_immune_center": {"immune_status": "stable"},
            "ai_runtime_integrity_center": {"integrity_score": 95, "integrity_status": "stable"},
            "ai_runtime_signal_intelligence": {"signal_status": "stable"},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
            "ai_runtime_adaptive_center": {"adaptive_status": "adaptive"},
            "ai_runtime_resilience_center": {"resilience_status": "resilient"},
        }

    def _urgent_dashboard(self):
        dashboard = self._dashboard()
        dashboard["ai_runtime_practical_console"] = {"console_status": "urgent"}
        dashboard["ai_dashboard_release_readiness_center"] = {"release_status": "blocked"}
        dashboard["ai_runtime_immune_center"] = {"immune_status": "critical"}
        dashboard["ai_runtime_integrity_center"] = {"integrity_score": 42}
        return dashboard

    def test_build_layered_home_returns_dict(self):
        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._dashboard())
        self.assertIsInstance(layered_home, dict)
        self.assertIn("layered_home_status", layered_home)

    def test_layers_count_is_seven(self):
        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._dashboard())
        self.assertEqual(len(layered_home["layers"]), 7)

    def test_each_layer_contains_modules(self):
        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._dashboard())
        for layer in layered_home["layers"]:
            self.assertIn("modules", layer)
            self.assertTrue(layer["modules"])

    def test_urgent_status_detected(self):
        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._urgent_dashboard())
        self.assertEqual(layered_home["layered_home_status"], "urgent")

    def test_recommended_entry_is_not_empty(self):
        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._dashboard())
        self.assertTrue(layered_home["recommended_entry"])

    def test_runtime_layered_home_export_route_registered(self):
        from web_ui.app import app

        layered_home = AIRuntimeLayeredHomeService.build_layered_home(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-layered-home-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_layered_home": layered_home}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-layered-home-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-layered-home-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-layered-home-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime OS 分层首页】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("层级".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime OS 分层首页".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_layered_home_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime OS 分层首页", template)


if __name__ == "__main__":
    unittest.main()
