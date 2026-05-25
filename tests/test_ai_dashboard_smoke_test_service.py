import unittest
from unittest.mock import patch

from services.ai_dashboard_smoke_test_service import AIDashboardSmokeTestService


class AIDashboardSmokeTestServiceTest(unittest.TestCase):
    def test_run_smoke_test_returns_status_and_checks(self):
        dashboard = {
            key: {}
            for key, _title in AIDashboardSmokeTestService.RUNTIME_MODULES
        }

        with patch("services.ai_dashboard_smoke_test_service.ArticleHealthService.build_ai_risk_dashboard", return_value=dashboard), \
             patch("services.ai_dashboard_smoke_test_service.ArticleHealthService.build_ai_dashboard_centers", return_value=dashboard), \
             patch.object(AIDashboardSmokeTestService, "_check_template_titles", side_effect=lambda checks: AIDashboardSmokeTestService._add_check(checks, "模板标题完整性", "passed", "ok")), \
             patch.object(AIDashboardSmokeTestService, "_check_export_routes", side_effect=lambda checks: AIDashboardSmokeTestService._add_check(checks, "导出路由完整性", "passed", "ok")), \
             patch.object(AIDashboardSmokeTestService, "_check_json_files", side_effect=lambda checks: AIDashboardSmokeTestService._add_check(checks, "JSON 文件健康", "passed", "ok")), \
             patch.object(AIDashboardSmokeTestService, "_check_json_error_tolerance", side_effect=lambda checks: AIDashboardSmokeTestService._add_check(checks, "JSON 损坏容错", "passed", "ok")):
            result = AIDashboardSmokeTestService.run_smoke_test()

        self.assertIn(result["status"], {"passed", "warning", "failed"})
        self.assertTrue(result["checks"])
        self.assertIn("failed_checks", result)
        self.assertIn("warning_checks", result)


if __name__ == "__main__":
    unittest.main()
