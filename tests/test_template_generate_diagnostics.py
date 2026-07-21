import unittest
from unittest.mock import patch

from web_ui.app import app


class TemplateGenerateDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"

    def test_success_logs_template_and_article_ids(self):
        with patch(
            "web_ui.app.TemplateService.use_template",
            return_value={"success": True, "article_id": 321},
        ), self.assertLogs(app.logger.name, level="INFO") as logs:
            response = self.client.post(
                "/templates/9/use",
                json={"topic": "银行审批逻辑", "template_key": "industry_law"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        output = "\n".join(logs.output)
        self.assertIn("[template-generate-start] template_id=9 topic=银行审批逻辑", output)
        self.assertIn("[template-generate-success] article_id=321", output)

    def test_exception_returns_real_error_and_logs_traceback(self):
        with patch(
            "web_ui.app.TemplateService.use_template",
            side_effect=RuntimeError("真实生成错误"),
        ), self.assertLogs(app.logger.name, level="ERROR") as logs:
            response = self.client.post(
                "/templates/9/use",
                json={"topic": "银行审批逻辑", "template_key": "industry_law"},
            )

        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "RuntimeError")
        self.assertEqual(data["error_message"], "真实生成错误")
        self.assertIn(
            "[template-generate-error] exception_type=RuntimeError exception_message=真实生成错误",
            "\n".join(logs.output),
        )
        self.assertTrue(any(record.exc_info for record in logs.records))

    def test_service_failure_is_normalized_for_frontend(self):
        with patch(
            "web_ui.app.TemplateService.use_template",
            return_value={"ok": False, "error_type": "GENERATION_FAILED", "error_message": "模型未返回正文"},
        ):
            response = self.client.post(
                "/templates/9/use",
                json={"topic": "银行审批逻辑", "template_key": "industry_law"},
            )

        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_message"], "模型未返回正文")


if __name__ == "__main__":
    unittest.main()