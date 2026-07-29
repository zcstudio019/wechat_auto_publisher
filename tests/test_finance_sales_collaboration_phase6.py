import unittest
from unittest.mock import MagicMock, patch

from services.finance_document_agent import FinanceDocumentAgent
from services.finance_followup_agent import FinanceFollowupAgent
from services.finance_project_pipeline_service import FinanceProjectPipelineService
from services.finance_sales_center_service import FinanceSalesCenterService
from services.finance_sales_funnel_analyzer import FinanceSalesFunnelAnalyzer
from services.finance_sales_script_agent import FinanceSalesScriptAgent
from tests.test_finance_advisor_agent_phase5 import customer_for_level
from web_ui.app import app


def build_hundred_customers():
    customers = []
    stages = FinanceProjectPipelineService.STAGES
    for level in ("S", "A", "B", "C", "D"):
        for index in range(20):
            customer = customer_for_level(level, index)
            global_index = len(customers)
            customer["id"] = global_index + 1
            customer["phone"] = f"138{global_index:08d}"
            customer["finance_stage"] = stages[global_index % len(stages)]
            customer["documents"] = (
                ["营业执照", "身份证", "流水", "财务报表", "纳税", "征信报告"]
                if level in {"S", "A"}
                else ["营业执照", "身份证"]
            )
            customers.append(customer)
    return customers


class FinanceFollowupAndScriptTestCase(unittest.TestCase):
    def test_followup_supports_all_customer_levels(self):
        expected_times = {
            "S": "1小时内",
            "A": "2小时内",
            "B": "24小时内",
            "C": "3天内",
            "D": "7天内",
        }
        for level, followup_time in expected_times.items():
            with self.subTest(level=level):
                result = FinanceFollowupAgent.generate(
                    {"level": level, "risks": ["测试风险"]},
                    customer={"name": "测试企业"},
                )
                self.assertEqual(result["level"], level)
                self.assertEqual(result["followup_time"], followup_time)
                self.assertTrue(result["customer_stage"])
                self.assertTrue(result["next_action"])
                self.assertTrue(result["communication_focus"])

    def test_sales_script_has_four_required_scripts_for_all_levels(self):
        for level in ("S", "A", "B", "C", "D"):
            result = FinanceSalesScriptAgent.generate(
                level,
                financing_need="企业周转500万元",
                risks=["现金流波动", "负债偏高"],
                customer_name="王总",
            )
            script_keys = (
                "first_call_script",
                "wechat_followup_script",
                "objection_handling_script",
                "closing_script",
            )
            for key in script_keys:
                self.assertTrue(result[key])
            self.assertIn("银行", " ".join(result[key] for key in script_keys))


class FinancePipelineAndDocumentTestCase(unittest.TestCase):
    def test_pipeline_advances_through_all_nine_stages(self):
        project = FinanceProjectPipelineService.create(
            {"id": 8, "name": "流程测试企业", "status": "new"},
            {"level": "S"},
        )
        visited = [project["current_stage"]]

        while project.get("next_stage"):
            project = FinanceProjectPipelineService.advance(project, note="测试推进")
            self.assertTrue(project["ok"])
            visited.append(project["current_stage"])

        self.assertEqual(tuple(visited), FinanceProjectPipelineService.STAGES)
        self.assertEqual(len(project["history"]), 8)
        self.assertEqual(project["progress_percent"], 100.0)

    def test_pipeline_rejects_stage_skipping(self):
        project = FinanceProjectPipelineService.create({"id": 1}, {"level": "A"})
        result = FinanceProjectPipelineService.advance(project, target_stage="融资诊断")
        self.assertFalse(result["ok"])
        self.assertIn("只能", result["error"])

    def test_document_agent_reports_required_existing_missing_and_risks(self):
        result = FinanceDocumentAgent.analyze(
            financing_type="抵押经营贷",
            bank_solution={"product_name": "抵押经营贷"},
            existing_documents=["营业执照", "法人身份证", "对公流水"],
        )

        self.assertIn("抵押物权属证明", result["required_documents"])
        self.assertEqual(len(result["existing_documents"]), 3)
        self.assertTrue(result["missing_documents"])
        self.assertLess(result["completion_rate"], 100)
        self.assertTrue(result["risk_notices"])


class FinanceSalesFunnelAndCenterTestCase(unittest.TestCase):
    def test_hundred_customers_generate_followups_scripts_pipeline_documents_and_funnel(self):
        center = FinanceSalesCenterService.build_center(build_hundred_customers())

        self.assertEqual(center["summary"]["total_customers"], 100)
        self.assertEqual(len(center["customers"]), 100)
        self.assertEqual(
            {item["diagnosis"]["level"] for item in center["customers"]},
            {"S", "A", "B", "C", "D"},
        )
        for item in center["customers"]:
            self.assertTrue(item["followup"]["next_action"])
            self.assertTrue(item["sales_scripts"]["first_call_script"])
            self.assertIn(item["project"]["current_stage"], FinanceProjectPipelineService.STAGES)
            self.assertTrue(item["documents"]["required_documents"])
        funnel = center["funnel"]
        self.assertEqual(funnel["lead_count"], 100)
        self.assertGreaterEqual(funnel["lead_count"], funnel["contact_count"])
        self.assertGreaterEqual(funnel["contact_count"], funnel["valid_customer_count"])
        self.assertGreaterEqual(funnel["valid_customer_count"], funnel["solution_count"])
        self.assertGreaterEqual(funnel["solution_count"], funnel["deal_count"])
        self.assertTrue(funnel["conversion_rates"])
        self.assertTrue(funnel["problem_nodes"])
        self.assertTrue(funnel["optimization_recommendations"])

    def test_funnel_detects_contact_bottleneck(self):
        projects = [
            {
                "project": {"current_stage": "线索进入", "level": "A"},
                "diagnosis": {"level": "A"},
            }
            for _ in range(10)
        ]
        result = FinanceSalesFunnelAnalyzer.analyze(projects)
        self.assertEqual(result["contact_rate"] if "contact_rate" in result else result["conversion_rates"]["contact_rate"], 0)
        self.assertIn("线索联系率偏低", result["problem_nodes"])


class FinanceSalesCenterRouteTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"

    def test_sales_center_page_displays_required_columns(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = build_hundred_customers()[:3]
        with patch("web_ui.app.get_db", return_value=connection):
            response = self.client.get("/finance-sales")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for label in (
            "AI融资销售中心",
            "客户",
            "评分",
            "等级",
            "当前阶段",
            "下一步动作",
            "话术",
            "资料状态",
        ):
            self.assertIn(label, html)

    def test_project_advance_api_returns_next_stage_without_database_write(self):
        project = FinanceProjectPipelineService.create({"id": 9}, {"level": "S"})
        response = self.client.post(
            "/api/finance-project/advance",
            json={"project": project, "note": "完成首次沟通"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["current_stage"], "初步沟通")

    def test_navigation_contains_finance_sales_center(self):
        with app.test_request_context("/finance-sales"):
            html = app.jinja_env.get_template("base.html").render(
                perms={"show_nav_business": True},
            )
        self.assertIn("/finance-sales", html)
        self.assertIn("AI融资销售中心", html)


if __name__ == "__main__":
    unittest.main()
