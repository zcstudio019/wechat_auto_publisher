import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_command_layer_service import AIRuntimeCommandLayerService
from services.ai_runtime_command_registry import get_runtime_command_registry


class AIRuntimeCommandLayerServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_entry_router": {
                "primary_entry": {
                    "title": "AI Dashboard 管理首页中心",
                    "route": "/ai-dashboard/home",
                    "reason": "normal",
                    "priority": "normal",
                },
                "router_status": "normal",
            },
            "ai_runtime_practical_console": {"console_status": "normal"},
            "ai_runtime_mission_control_center": {"mission_status": "normal"},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
            "ai_dashboard_release_readiness_center": {"release_status": "ready"},
            "ai_dashboard_export_operations_center": {"operations_status": "normal"},
            "ai_runtime_immune_center": {"immune_status": "stable"},
            "ai_runtime_integrity_center": {"integrity_status": "stable", "integrity_score": 95},
            "ai_runtime_judgment_center": {"judgment_status": "stable"},
        }

    def test_registry_is_not_empty(self):
        registry = get_runtime_command_registry()
        self.assertTrue(registry)

    def test_command_key_is_unique(self):
        registry = get_runtime_command_registry()
        keys = [command["command_key"] for command in registry]
        self.assertEqual(len(keys), len(set(keys)))

    def test_build_command_layer_returns_dict(self):
        command_layer = AIRuntimeCommandLayerService.build_command_layer(self._dashboard())
        self.assertIsInstance(command_layer, dict)
        self.assertIn("command_layer_status", command_layer)

    def test_recommended_commands_is_list(self):
        command_layer = AIRuntimeCommandLayerService.build_command_layer(self._dashboard())
        self.assertIsInstance(command_layer["recommended_commands"], list)

    def test_blocked_commands_is_list(self):
        dashboard = self._dashboard()
        dashboard["ai_dashboard_release_readiness_center"] = {"release_status": "blocked"}
        command_layer = AIRuntimeCommandLayerService.build_command_layer(dashboard)
        self.assertIsInstance(command_layer["blocked_commands"], list)

    def test_human_review_commands_is_list(self):
        dashboard = self._dashboard()
        dashboard["ai_runtime_immune_center"] = {"immune_status": "critical", "immune_alerts": ["alert"]}
        command_layer = AIRuntimeCommandLayerService.build_command_layer(dashboard)
        self.assertIsInstance(command_layer["human_review_commands"], list)
        self.assertTrue(command_layer["human_review_commands"])

    def test_runtime_command_layer_export_route_registered(self):
        from web_ui.app import app

        command_layer = AIRuntimeCommandLayerService.build_command_layer(self._dashboard())
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-command-layer-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_command_layer": command_layer}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-command-layer-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-command-layer-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-command-layer-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 命令层】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("命令".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 命令层".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_command_layer_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 命令层", template)

    def test_no_automatic_command_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_command_layer_service.py").read_text(encoding="utf-8")
        registry_source = Path("services/ai_runtime_command_registry.py").read_text(encoding="utf-8")
        combined = service_source + registry_source
        for forbidden in [
            "def execute",
            "def dispatch",
            "def run",
            "worker",
            "scheduler",
            "subprocess",
            "requests.",
            "publish_approved_articles",
        ]:
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
