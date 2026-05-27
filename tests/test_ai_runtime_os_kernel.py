import unittest
from unittest.mock import patch

from services.ai_runtime_layer_registry import get_runtime_center_manifests
from services.ai_runtime_os_kernel import AIRuntimeOSKernel
from services.ai_runtime_state_bus import AIRuntimeStateBus


class AIRuntimeOSKernelTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {item["key"]: {"summary": "ok"} for item in get_runtime_center_manifests()}

    def test_registry_not_empty(self):
        self.assertTrue(get_runtime_center_manifests())

    def test_registry_covers_core_dashboard_keys(self):
        keys = {item["key"] for item in get_runtime_center_manifests()}
        required = {
            "ai_dashboard_admin_home_center",
            "ai_dashboard_production_hardening_center",
            "ai_dashboard_navigation_index_center",
            "ai_runtime_observability_center",
            "ai_runtime_executive_dashboard",
            "ai_runtime_continuous_improvement_center",
        }
        self.assertTrue(required.issubset(keys))

    def test_state_bus_get_state(self):
        bus = AIRuntimeStateBus({"ai_runtime_observability_center": {"status": "ok"}})
        self.assertEqual(bus.get_state("ai_runtime_observability_center"), {"status": "ok"})

    def test_state_bus_missing_key_fallback(self):
        bus = AIRuntimeStateBus({})
        self.assertEqual(bus.get_state("missing_key", default="fallback"), "fallback")

    def test_validate_required_keys(self):
        bus = AIRuntimeStateBus(self._dashboard_fixture())
        self.assertEqual(bus.validate_required_keys(), [])

    def test_build_kernel_view_returns_dict(self):
        view = AIRuntimeOSKernel.build_kernel_view(self._dashboard_fixture())
        self.assertIsInstance(view, dict)
        self.assertIn("kernel_status", view)
        self.assertIn("layers", view)

    def test_missing_required_key_is_critical(self):
        dashboard = self._dashboard_fixture()
        dashboard.pop("ai_runtime_observability_center")
        view = AIRuntimeOSKernel.build_kernel_view(dashboard)
        self.assertEqual(view["kernel_status"], "critical")
        self.assertIn("ai_runtime_observability_center", view["missing_required_keys"])

    def test_normal_dashboard_is_healthy_or_warning(self):
        view = AIRuntimeOSKernel.build_kernel_view(self._dashboard_fixture())
        self.assertIn(view["kernel_status"], {"healthy", "warning"})

    def test_markdown_export_contains_title(self):
        markdown = AIRuntimeOSKernel.build_kernel_markdown(
            AIRuntimeOSKernel.build_kernel_view(self._dashboard_fixture())
        )
        self.assertIn("# AI Runtime 操作系统内核", markdown)

    def test_runtime_os_kernel_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-os-kernel-export", rules)

        kernel_view = AIRuntimeOSKernel.build_kernel_view(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_os_kernel": kernel_view}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-os-kernel-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-os-kernel-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-os-kernel-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 操作系统内核】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 操作系统内核".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_runtime_os_kernel_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 操作系统内核", template)


if __name__ == "__main__":
    unittest.main()
