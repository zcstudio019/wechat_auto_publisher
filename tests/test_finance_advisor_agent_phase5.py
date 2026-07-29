import unittest
from unittest.mock import MagicMock, patch

from services.finance_advisor_center_service import FinanceAdvisorCenterService
from services.finance_diagnosis_agent import FinanceDiagnosisAgent
from services.finance_product_match_agent import FinanceProductMatchAgent
from services.finance_report_generator import FinanceReportGenerator
from services.finance_sales_assistant_agent import FinanceSalesAssistantAgent
from web_ui.app import app


def customer_for_level(level: str, index: int = 0) -> dict:
    base = {"id": index + 1, "name": f"{level}级企业{index + 1}", "industry": "制造业"}
    if level == "S":
        return {
            **base,
            "business_years": 5,
            "annual_revenue": 8_000_000,
            "operating_status": "稳定盈利",
            "annual_cash_inflow": 9_000_000,
            "monthly_repayment": 100_000,
            "debt_ratio": "25%",
            "credit_status": "良好无逾期",
            "financing_need": "设备采购",
            "financing_amount": 2_000_000,
            "timeline": "本月",
            "documents": [],
        }
    if level == "A":
        return {
            **base,
            "business_years": 4,
            "annual_revenue": 2_000_000,
            "operating_status": "稳定",
            "cash_flow_status": "稳定",
            "debt_ratio": "45%",
            "credit_status": "良好",
            "financing_need": "企业周转",
            "financing_amount": 800_000,
        }
    if level == "B":
        return {
            **base,
            "business_years": 2,
            "annual_revenue": 1_200_000,
            "operating_status": "正常",
            "debt_ratio": "65%",
            "credit_status": "轻微查询偏多",
            "financing_need": "库存备货",
            "financing_amount": 500_000,
            "timeline": "30天内",
        }
    if level == "C":
        return {
            **base,
            "business_years": 1,
            "annual_revenue": 500_000,
            "operating_status": "稳定",
            "cash_flow_status": "紧张",
            "credit_status": "轻微查询",
            "financing_need": "想了解经营贷",
            "financing_amount": 200_000,
        }
    return base


class FinanceDiagnosisAgentTestCase(unittest.TestCase):
    def test_diagnosis_has_required_json_fields_and_weights(self):
        result = FinanceDiagnosisAgent.diagnose(customer_for_level("S"))

        for key in (
            "score",
            "level",
            "financing_capacity",
            "advantages",
            "risks",
            "problems",
            "recommendations",
            "required_documents",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["level"], "S")
        self.assertEqual(result["score_detail"], {
            "enterprise_operation": 30,
            "cash_flow": 25,
            "debt": 20,
            "credit": 15,
            "financing_need": 10,
        })

    def test_fifty_enterprises_cover_all_diagnosis_levels(self):
        customers = [
            customer_for_level(level, index)
            for level in ("S", "A", "B", "C", "D")
            for index in range(10)
        ]

        center = FinanceAdvisorCenterService.build_center(customers)

        self.assertEqual(center["summary"]["total_customers"], 50)
        self.assertEqual(set(center["summary"]["levels"]), {"S", "A", "B", "C", "D"})
        self.assertEqual(center["summary"]["levels"], {
            "S": 10,
            "A": 10,
            "B": 10,
            "C": 10,
            "D": 10,
        })


class FinanceProductReportAndSalesTestCase(unittest.TestCase):
    def test_product_match_prefers_explicit_existing_library(self):
        customer = customer_for_level("S")
        products = [{
            "name": "现有银行订单贷",
            "type": "supply_chain",
            "quota": "50万-800万元",
            "duration": "12个月",
            "keywords": ["设备采购", "订单"],
            "min_business_years": 2,
            "risk": "需核验真实订单和回款。",
        }]

        result = FinanceProductMatchAgent.match(customer, products=products)

        self.assertEqual(result["product_library_source"], "existing_product_library")
        self.assertEqual(result["matches"][0]["product_name"], "现有银行订单贷")
        for key in ("match_reason", "amount", "term", "risk_notice"):
            self.assertIn(key, result["matches"][0])

    def test_product_match_uses_safe_fallback_when_library_is_absent(self):
        result = FinanceProductMatchAgent.match(customer_for_level("A"))

        self.assertEqual(result["product_library_source"], "phase5_fallback_library")
        self.assertTrue(result["matches"])
        self.assertIn("不构成银行授信承诺", result["disclaimer"])

    def test_report_contains_all_required_sections(self):
        report = FinanceReportGenerator.generate(customer_for_level("S"))

        for key in (
            "enterprise_profile",
            "financing_score",
            "bank_review_analysis",
            "problem_diagnosis",
            "optimization_recommendations",
            "solution_recommendations",
            "required_documents",
        ):
            self.assertIn(key, report)
        for heading in (
            "企业画像",
            "融资评分",
            "银行审核分析",
            "问题诊断",
            "优化建议",
            "方案推荐",
            "资料清单",
        ):
            self.assertIn(heading, report["report_text"])

    def test_sales_assistant_generates_level_specific_actions(self):
        for level in ("S", "A", "B", "C", "D"):
            with self.subTest(level=level):
                result = FinanceSalesAssistantAgent.generate(
                    {"name": "测试老板", "financing_need": "企业周转"},
                    {"level": level},
                )
                self.assertEqual(result["level"], level)
                self.assertTrue(result["follow_actions"])
                self.assertTrue(result["communication_focus"])
                self.assertTrue(result["risk_alerts"])
                self.assertTrue(result["next_tasks"])


class FinanceDiagnosisCenterRouteTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"

    def test_diagnosis_api_returns_complete_result(self):
        response = self.client.post(
            "/api/finance-diagnosis",
            json=customer_for_level("S"),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["diagnosis"]["level"], "S")
        self.assertTrue(data["product_matches"]["matches"])
        self.assertTrue(data["report"]["report_text"])
        self.assertTrue(data["sales_assistance"]["follow_actions"])

    def test_diagnosis_center_page_displays_required_columns(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [
            customer_for_level("S", 1),
            customer_for_level("B", 2),
        ]
        with patch("web_ui.app.get_db", return_value=connection):
            response = self.client.get("/finance-diagnosis")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for label in ("AI融资诊断中心", "客户", "评分", "等级", "融资需求", "匹配方案", "跟进建议"):
            self.assertIn(label, html)

    def test_navigation_contains_diagnosis_center(self):
        with app.test_request_context("/finance-diagnosis"):
            html = app.jinja_env.get_template("base.html").render(
                perms={"show_nav_business": True},
            )
        self.assertIn("/finance-diagnosis", html)
        self.assertIn("AI融资诊断中心", html)


if __name__ == "__main__":
    unittest.main()
