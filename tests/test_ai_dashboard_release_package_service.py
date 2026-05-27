import unittest
from unittest.mock import Mock, patch

from services.ai_dashboard_release_package_service import AIDashboardReleasePackageService


class AIDashboardReleasePackageServiceTest(unittest.TestCase):
    def _readiness(self, status="ready"):
        return {
            "release_status": status,
            "readiness_status": status,
            "readiness_score": 92 if status == "ready" else 68,
            "release_level": "L1 可上线" if status == "ready" else "L2 有条件上线",
            "summary": "release ok",
            "warning_checks": [] if status == "ready" else [{"name": "warning", "status": "warning", "summary": "warn"}],
            "blocking_checks": [{"name": "block", "status": "blocked", "summary": "block"}] if status == "blocked" else [],
            "rollback_readiness": [{"item": "Git tag", "status": "manual", "summary": "tag"}],
            "recommended_actions": ["导出上线包报告"],
        }

    def _smoke(self, status="passed", failed_count=0):
        return {"status": status, "failed_count": failed_count, "summary": "smoke ok"}

    def _hardening(self, status="healthy"):
        return {
            "hardening_status": status,
            "summary": "hardening ok",
            "deployment_checklist": [{"item": "HTTPS", "status": "manual", "summary": "check"}],
            "production_risks": [] if status == "healthy" else [{"risk": "route", "status": "warning", "summary": "warn"}],
            "high_risk_gaps": [{"risk": "gap", "status": "critical", "summary": "risk"}] if status == "critical" else [],
        }

    def _ops(self, status="healthy"):
        return {"health_status": status, "summary": "ops ok", "recommended_actions": ["watch ops"]}

    def _documentation(self):
        return {
            "documentation_status": "complete",
            "summary": "docs ok",
            "module_catalog": [{"module_name": "Runtime"}],
            "route_docs": [{"route": "/ai-dashboard"}],
        }

    def _architecture(self):
        return {
            "architecture_status": "stable",
            "summary": "arch ok",
            "runtime_layers": [{"layer": "Runtime", "modules": ["Snapshot"]}],
            "data_dependencies": [{"name": "data"}],
            "architecture_risks": [],
        }

    def _navigation(self):
        return {"navigation_status": "clear", "summary": "nav ok"}

    def _export_ops(self):
        return {"operation_status": "normal", "summary": "export ok"}

    def _digest(self):
        return {"digest_status": "stable", "one_line_summary": "runtime ok", "summary": "digest ok"}

    def _patch_dependencies(self, readiness=None, smoke=None, hardening=None):
        return patch.multiple(
            "services.ai_dashboard_release_package_service",
            AIDashboardReleaseReadinessService=Mock(
                build_release_readiness_center=Mock(return_value=readiness or self._readiness())
            ),
            AIDashboardSmokeTestService=Mock(
                run_smoke_test=Mock(return_value=smoke or self._smoke())
            ),
            AIDashboardProductionHardeningService=Mock(
                build_production_hardening_center=Mock(return_value=hardening or self._hardening())
            ),
            AIDashboardOpsHealthService=Mock(
                build_ops_health_center=Mock(return_value=self._ops())
            ),
            AIDashboardDocumentationService=Mock(
                build_documentation_center=Mock(return_value=self._documentation())
            ),
            AIDashboardArchitectureMapService=Mock(
                build_architecture_map=Mock(return_value=self._architecture())
            ),
            AIDashboardNavigationService=Mock(
                build_navigation_center=Mock(return_value=self._navigation())
            ),
            AIDashboardExportOperationsService=Mock(
                build_export_operations_center=Mock(return_value=self._export_ops())
            ),
            AIRuntimeExecutiveDigestService=Mock(
                build_executive_digest=Mock(return_value=self._digest())
            ),
        )

    def test_build_release_package_center_returns_required_fields(self):
        with self._patch_dependencies():
            center = AIDashboardReleasePackageService.build_release_package_center()
        for key in [
            "package_status",
            "package_version",
            "release_readiness_snapshot",
            "production_hardening_snapshot",
            "ops_health_snapshot",
            "runtime_safety_snapshot",
            "included_modules",
            "included_routes",
            "included_templates",
            "included_services",
            "included_exports",
            "package_checklist",
            "blocking_issues",
            "manual_confirmation_items",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_release_readiness_blocked_blocks_package(self):
        with self._patch_dependencies(readiness=self._readiness("blocked")):
            center = AIDashboardReleasePackageService.build_release_package_center()
        self.assertEqual(center["package_status"], "blocked")

    def test_release_readiness_warning_makes_package_draft(self):
        with self._patch_dependencies(readiness=self._readiness("conditional")):
            center = AIDashboardReleasePackageService.build_release_package_center()
        self.assertEqual(center["package_status"], "draft")

    def test_release_readiness_ready_makes_package_packaged(self):
        with self._patch_dependencies():
            center = AIDashboardReleasePackageService.build_release_package_center()
        self.assertEqual(center["package_status"], "packaged")

    def test_exports_have_required_title_and_rows(self):
        with self._patch_dependencies():
            center = AIDashboardReleasePackageService.build_release_package_center()
        self.assertIn("【AI Dashboard 上线包中心】", AIDashboardReleasePackageService.build_release_package_text(center))
        rows = AIDashboardReleasePackageService.build_release_package_rows(center)
        self.assertTrue(rows)
        self.assertIn("分类", rows[0])
        self.assertIn("是否阻塞", rows[0])
        self.assertIn("是否需要人工确认", rows[0])

    def test_routes_registered_and_exports_accessible(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/release-package", rules)
        self.assertIn("/ai-dashboard/release-package-export", rules)

        center = {
            "package_status": "packaged",
            "package_version": "ai-dashboard-test",
            "summary": "ok",
            "release_readiness_snapshot": {},
            "production_hardening_snapshot": {},
            "ops_health_snapshot": {},
            "runtime_safety_snapshot": {},
            "included_modules": [],
            "included_routes": [],
            "included_templates": [],
            "included_services": [],
            "included_exports": [],
            "package_checklist": [],
            "blocking_issues": [],
            "manual_confirmation_items": [],
            "recommended_actions": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardReleasePackageService.build_release_package_center", return_value=center):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/release-package")
                txt_response = client.get("/ai-dashboard/release-package-export?format=txt")
                csv_response = client.get("/ai-dashboard/release-package-export?format=csv")
                md_response = client.get("/ai-dashboard/release-package-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 上线包中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)

    def test_dashboard_template_contains_release_package_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 上线包中心", template)
        self.assertIn("查看上线包详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("当前暂无 Dashboard 上线包数据。", template)
        self.assertIn("ai_dashboard_release_package_center", template)


if __name__ == "__main__":
    unittest.main()
