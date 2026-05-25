import unittest
from unittest.mock import patch

from services.ai_dashboard_architecture_map_service import AIDashboardArchitectureMapService


class AIDashboardArchitectureMapServiceTest(unittest.TestCase):
    def test_build_architecture_map_returns_dict(self):
        center = AIDashboardArchitectureMapService.build_architecture_map()
        self.assertIsInstance(center, dict)
        self.assertIn("architecture_status", center)
        self.assertIn("runtime_layers", center)
        self.assertIn("control_centers", center)
        self.assertIn("manual_boundaries", center)
        self.assertIn("read_only_boundaries", center)

    def test_runtime_layers_are_built(self):
        center = AIDashboardArchitectureMapService.build_architecture_map()
        layers = {item["layer"] for item in center["runtime_layers"]}
        self.assertIn("Executive Layer", layers)
        self.assertIn("Export/Ops Layer", layers)
        self.assertIn("Constitution Layer", layers)

    def test_module_relationships_are_built(self):
        center = AIDashboardArchitectureMapService.build_architecture_map()
        pairs = {(item["source"], item["target"]) for item in center["module_relationships"]}
        self.assertIn(("Forecast", "Predictive Action"), pairs)
        self.assertIn(("Ops Health", "Ops Maintenance"), pairs)

    def test_risk_propagation_paths_are_built(self):
        center = AIDashboardArchitectureMapService.build_architecture_map()
        summaries = [item["summary"] for item in center["risk_propagation_paths"]]
        self.assertTrue(any("Smoke Test fail" in item for item in summaries))

    def test_boundaries_are_built(self):
        center = AIDashboardArchitectureMapService.build_architecture_map()
        automation = {item["module"] for item in center["automation_boundaries"]}
        human = {item["module"] for item in center["human_boundaries"]}
        readonly = {item["module"] for item in center["readonly_boundaries"]}
        self.assertIn("Ops Health", automation)
        self.assertIn("发布", human)
        self.assertIn("Forecast", readonly)

    def test_architecture_status_stable_warning_and_risky(self):
        stable = AIDashboardArchitectureMapService.build_architecture_map()
        self.assertEqual(stable["architecture_status"], "normal")

        with patch.object(AIDashboardArchitectureMapService, "BOUNDARIES_CLEAR", False):
            warning = AIDashboardArchitectureMapService.build_architecture_map()
        self.assertEqual(warning["architecture_status"], "warning")

        with patch.object(AIDashboardArchitectureMapService, "SINGLE_POINT_RISKS", [f"risk-{i}" for i in range(6)]):
            risky = AIDashboardArchitectureMapService.build_architecture_map()
        self.assertEqual(risky["architecture_status"], "critical")

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/architecture-map", rules)
        self.assertIn("/ai-dashboard/architecture-map-export", rules)

        fixture = {
            "architecture_status": "normal",
            "summary": "ok",
            "runtime_layers": [],
            "module_relationships": [],
            "data_dependencies": [],
            "risk_propagation_paths": [],
            "automation_boundaries": [],
            "human_boundaries": [],
            "readonly_boundaries": [],
            "control_centers": [],
            "manual_boundaries": [],
            "read_only_boundaries": [],
            "core_control_centers": [],
            "high_coupling_modules": [],
            "single_point_risks": [],
            "architecture_risks": [],
            "recommended_actions": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardArchitectureMapService.build_architecture_map", return_value=fixture):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/architecture-map")
                txt_response = client.get("/ai-dashboard/architecture-map-export?format=txt")
                csv_response = client.get("/ai-dashboard/architecture-map-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 系统架构地图中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
