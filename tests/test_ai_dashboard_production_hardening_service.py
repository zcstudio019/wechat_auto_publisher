import unittest

from services.ai_dashboard_production_hardening_service import AIDashboardProductionHardeningService


class AIDashboardProductionHardeningServiceTest(unittest.TestCase):
    def test_build_production_hardening_center_returns_dict(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertIsInstance(center, dict)
        self.assertIn("hardening_status", center)
        self.assertIn("permission_checks", center)
        self.assertIn("production_risks", center)

        required_keys = [
            "security_checklist",
            "runtime_safety_checklist",
            "export_safety_checklist",
            "ops_safety_checklist",
            "permission_checklist",
            "route_hardening_checklist",
            "json_file_hardening_checklist",
            "template_hardening_checklist",
            "deployment_checklist",
            "high_risk_gaps",
            "recommended_actions",
        ]
        for key in required_keys:
            self.assertIn(key, center)

    def test_permission_checks_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["permission_checks"])

    def test_route_security_checks_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["route_security_checks"])

    def test_export_file_security_checks_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["export_file_security_checks"])

    def test_json_backup_checks_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["json_backup_checks"])

    def test_deployment_checklist_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["deployment_checklist"])

    def test_audit_log_suggestions_not_empty(self):
        center = AIDashboardProductionHardeningService.build_production_hardening_center()
        self.assertTrue(center["audit_log_suggestions"])

    def test_text_export_contains_title(self):
        text = AIDashboardProductionHardeningService.build_production_hardening_text(
            AIDashboardProductionHardeningService.build_production_hardening_center()
        )
        self.assertIn("【AI Dashboard 生产级加固】", text)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/production-hardening", rules)
        self.assertIn("/ai-dashboard/production-hardening-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            response = client.get("/ai-dashboard/production-hardening")
            txt_response = client.get("/ai-dashboard/production-hardening-export?format=txt")
            csv_response = client.get("/ai-dashboard/production-hardening-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 生产级加固".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Dashboard 生产级加固】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)

    def test_dashboard_template_contains_production_hardening_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 生产级加固", template)
        self.assertIn("查看生产级加固详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("当前暂无 Dashboard 生产级加固数据。", template)
        self.assertIn("ai_dashboard_production_hardening_center", template)


if __name__ == "__main__":
    unittest.main()
