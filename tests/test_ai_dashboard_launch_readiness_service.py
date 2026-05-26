import unittest
from unittest.mock import patch

from services.ai_dashboard_launch_readiness_service import AIDashboardLaunchReadinessService


class AIDashboardLaunchReadinessServiceTest(unittest.TestCase):
    def _release(self, status="ready", blocking=None):
        return {
            "release_status": status,
            "blocking_checks": blocking or [],
            "deployment_checklist": [{"item": "py_compile", "status": "manual", "summary": "run compile"}],
            "recommended_actions": ["备份 data 目录"],
        }

    def _hardening(self, status="safe"):
        return {
            "hardening_status": status,
            "summary": "hardening ok",
            "route_hardening_checklist": [{"name": "关键路由权限", "status": "pass", "summary": "ok"}],
            "template_hardening_checklist": [{"name": "空态兜底", "status": "manual_required", "summary": "check"}],
            "permission_checklist": [{"route": "/ai-dashboard", "status": "pass", "summary": "ok"}],
            "json_file_hardening_checklist": [{"file": "data.json", "status": "warning", "summary": "backup"}],
            "deployment_checklist": [{"item": "HTTPS", "status": "manual", "summary": "manual"}],
        }

    def _ops(self, status="healthy"):
        return {"health_status": status, "summary": "ops ok"}

    def _export_ops(self, status="normal"):
        return {"operation_status": status, "summary": "export ok"}

    def _patch_dependencies(self, release=None, hardening=None, ops=None, export_ops=None):
        return patch.multiple(
            "services.ai_dashboard_launch_readiness_service",
            AIDashboardReleaseReadinessService=unittest.mock.Mock(
                build_release_readiness_center=unittest.mock.Mock(return_value=release or self._release())
            ),
            AIDashboardProductionHardeningService=unittest.mock.Mock(
                build_production_hardening_center=unittest.mock.Mock(return_value=hardening or self._hardening())
            ),
            AIDashboardOpsHealthService=unittest.mock.Mock(
                build_ops_health_center=unittest.mock.Mock(return_value=ops or self._ops())
            ),
            AIDashboardExportOperationsService=unittest.mock.Mock(
                build_export_operations_center=unittest.mock.Mock(return_value=export_ops or self._export_ops())
            ),
        )

    def test_build_launch_readiness_center_returns_required_fields(self):
        with self._patch_dependencies():
            center = AIDashboardLaunchReadinessService.build_launch_readiness_center()
        self.assertIsInstance(center, dict)
        for key in [
            "readiness_status",
            "readiness_score",
            "summary",
            "production_hardening_status",
            "runtime_safety_status",
            "ops_health_status",
            "export_system_status",
            "route_readiness",
            "template_readiness",
            "permission_readiness",
            "data_file_readiness",
            "deployment_readiness",
            "blocking_issues",
            "go_live_checklist",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_ready_status_and_score(self):
        with self._patch_dependencies():
            center = AIDashboardLaunchReadinessService.build_launch_readiness_center()
        self.assertEqual(center["readiness_status"], "ready")
        self.assertGreaterEqual(center["readiness_score"], 1)

    def test_blocking_issue_blocks_launch(self):
        release = self._release("blocked", blocking=[{"name": "Smoke Test", "status": "blocked", "summary": "failed"}])
        with self._patch_dependencies(release=release):
            center = AIDashboardLaunchReadinessService.build_launch_readiness_center()
        self.assertEqual(center["readiness_status"], "blocked")
        self.assertTrue(center["blocking_issues"])

    def test_exports_contain_title_and_rows(self):
        with self._patch_dependencies():
            center = AIDashboardLaunchReadinessService.build_launch_readiness_center()
        self.assertIn("【AI Dashboard 上线准备度中心】", AIDashboardLaunchReadinessService.build_launch_readiness_text(center))
        rows = AIDashboardLaunchReadinessService.build_launch_readiness_rows(center)
        self.assertTrue(rows)
        self.assertIn("分类", rows[0])

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/launch-readiness", rules)
        self.assertIn("/ai-dashboard/launch-readiness-export", rules)

        app.config["TESTING"] = True
        with patch(
            "web_ui.app.AIDashboardLaunchReadinessService.build_launch_readiness_center",
            return_value={
                "readiness_status": "ready",
                "readiness_score": 90,
                "summary": "ok",
                "production_hardening_status": {},
                "runtime_safety_status": {},
                "ops_health_status": {},
                "export_system_status": {},
                "route_readiness": [],
                "template_readiness": [],
                "permission_readiness": [],
                "data_file_readiness": [],
                "deployment_readiness": [],
                "blocking_issues": [],
                "go_live_checklist": [],
                "recommended_actions": [],
            },
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/launch-readiness")
                txt_response = client.get("/ai-dashboard/launch-readiness-export?format=txt")
                csv_response = client.get("/ai-dashboard/launch-readiness-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 上线准备度中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Dashboard 上线准备度中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)

    def test_dashboard_template_contains_launch_readiness_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 上线准备度中心", template)
        self.assertIn("查看上线准备度详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("当前暂无 Dashboard 上线准备度数据。", template)
        self.assertIn("ai_dashboard_launch_readiness_center", template)


if __name__ == "__main__":
    unittest.main()
