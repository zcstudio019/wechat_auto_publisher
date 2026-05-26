import unittest
from unittest.mock import patch

from services.ai_dashboard_release_readiness_service import AIDashboardReleaseReadinessService


class AIDashboardReleaseReadinessServiceTest(unittest.TestCase):
    def _smoke(self, status="passed", failed_count=0):
        return {"status": status, "failed_count": failed_count, "summary": "smoke ok"}

    def _hardening(self, status="safe"):
        return {
            "hardening_status": status,
            "summary": "hardening ok",
            "permission_checks": [],
            "route_security_checks": [],
            "json_backup_checks": [],
            "large_file_risk_checks": [],
            "timeout_risk_checks": [],
        }

    def _ops(self, status="healthy"):
        return {"ops_status": status, "summary": "ops ok", "notification_status": {"email_enabled": True, "webhook_enabled": True}}

    def _patch_dependencies(self, smoke=None, hardening=None, ops=None, maintenance=None, export_ops=None):
        return patch.multiple(
            "services.ai_dashboard_release_readiness_service",
            AIDashboardSmokeTestService=unittest.mock.Mock(run_smoke_test=unittest.mock.Mock(return_value=smoke or self._smoke())),
            AIDashboardProductionHardeningService=unittest.mock.Mock(build_production_hardening_center=unittest.mock.Mock(return_value=hardening or self._hardening())),
            AIDashboardOpsHealthService=unittest.mock.Mock(build_ops_health_center=unittest.mock.Mock(return_value=ops or self._ops())),
            AIDashboardOpsMaintenanceService=unittest.mock.Mock(build_maintenance_plan=unittest.mock.Mock(return_value=maintenance or {"maintenance_status": "normal", "summary": "maintenance ok"})),
            AIDashboardExportOperationsService=unittest.mock.Mock(build_export_operations_center=unittest.mock.Mock(return_value=export_ops or {"operations_status": "normal", "summary": "export ok"})),
            AIDashboardDocumentationService=unittest.mock.Mock(build_documentation_center=unittest.mock.Mock(return_value={"summary": "docs ok"})),
            AIDashboardNavigationService=unittest.mock.Mock(build_navigation_center=unittest.mock.Mock(return_value={"summary": "nav ok"})),
            AIDashboardArchitectureMapService=unittest.mock.Mock(build_architecture_map=unittest.mock.Mock(return_value={"summary": "arch ok"})),
        )

    def test_build_release_readiness_center_returns_dict(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertIsInstance(center, dict)
        self.assertIn("release_status", center)

    def test_smoke_fail_blocks_release(self):
        with self._patch_dependencies(smoke=self._smoke("failed", 1)):
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertEqual(center["release_status"], "blocked")

    def test_hardening_risky_blocks_release(self):
        with self._patch_dependencies(hardening=self._hardening("risky")):
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertEqual(center["release_status"], "blocked")

    def test_warnings_make_conditional(self):
        hardening = self._hardening("warning")
        hardening["json_backup_checks"] = [{"status": "warning", "summary": "backup missing"}]
        with self._patch_dependencies(hardening=hardening):
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertEqual(center["release_status"], "conditional")

    def test_safe_is_ready(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertEqual(center["release_status"], "ready")

    def test_rollback_readiness_not_empty(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertTrue(center["rollback_readiness"])

    def test_deployment_checklist_not_empty(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseReadinessService.build_release_readiness_center()
        self.assertTrue(center["deployment_checklist"])

    def test_markdown_export_contains_title(self):
        with self._patch_dependencies():
            markdown = AIDashboardReleaseReadinessService.build_release_readiness_markdown()
        self.assertIn("# AI Dashboard 上线准备度中心", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/release-readiness", rules)
        self.assertIn("/ai-dashboard/release-readiness-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardReleaseReadinessService.build_release_readiness_center", return_value={"release_status": "ready", "release_level": "L1 可上线", "summary": "ok", "passed_checks": [], "warning_checks": [], "blocking_checks": [], "acceptable_risks": [], "must_fix_before_release": [], "rollback_readiness": [], "ops_readiness": [], "deployment_checklist": [], "recommended_actions": []}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/release-readiness")
                txt_response = client.get("/ai-dashboard/release-readiness-export?format=txt")
                csv_response = client.get("/ai-dashboard/release-readiness-export?format=csv")
                md_response = client.get("/ai-dashboard/release-readiness-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 上线准备度中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)

    def test_dashboard_template_contains_release_readiness_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 上线准备度中心", template)
        self.assertIn("查看上线准备详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("导出 Markdown", template)


if __name__ == "__main__":
    unittest.main()
