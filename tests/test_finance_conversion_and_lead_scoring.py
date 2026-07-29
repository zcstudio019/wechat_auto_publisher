import unittest

from services.enterprise_finance_content_library import match_finance_cta
from services.finance_conversion_tracker import FinanceConversionTracker
from services.finance_lead_scoring_agent import FinanceLeadScoringAgent


def _articles(count=20):
    pain_points = ("额度不足", "现金流紧张", "征信问题", "银行拒贷")
    return [
        {
            "id": index + 1,
            "title": f"企业老板融资场景文章{index + 1}",
            "category": "industry_law",
            "conversion_goal": match_finance_cta(
                {"pain_point": pain_points[index % len(pain_points)]}
            )["title"],
            "view_count": 3000 - index * 80,
            "click_count": 180 - index * 4,
            "wechat_add_count": 90 - index * 2,
            "consult_count": 50 - index,
            "deal_count": max(0, 12 - index // 2),
        }
        for index in range(count)
    ]


class FinanceConversionTrackerTestCase(unittest.TestCase):
    def test_simulated_twenty_articles_generate_ranking_funnel_and_recommendations(self):
        articles = _articles()
        articles.append({
            "id": 999,
            "title": "普通品牌宣传文章",
            "category": "brand",
            "view_count": 999999,
            "deal_count": 999,
        })

        result = FinanceConversionTracker.analyze_articles(articles)

        self.assertEqual(result["summary"]["total_articles"], 20)
        self.assertEqual(len(result["records"]), 20)
        self.assertNotIn(999, [item["article_id"] for item in result["records"]])
        self.assertEqual(result["ranking"][0]["article_id"], 1)
        self.assertTrue(result["recommendations"])
        self.assertGreater(result["recommendations"][0]["value_score"], 0)
        funnel = result["funnel"]
        self.assertGreaterEqual(funnel["read_count"], funnel["consult_count"])
        self.assertGreaterEqual(funnel["consult_count"], funnel["lead_count"])
        self.assertGreaterEqual(funnel["lead_count"], funnel["valid_lead_count"])
        self.assertGreaterEqual(funnel["valid_lead_count"], funnel["deal_count"])

    def test_existing_metrics_have_compatible_conversion_aliases(self):
        tracker = FinanceConversionTracker()
        result = tracker.record({
            "id": 8,
            "title": "银行拒贷后怎么处理",
            "article_type": "industry_law",
            "conversion_goal": "贷款失败原因分析",
            "view_count": 100,
            "scan_count": 12,
            "consult_count": 5,
            "deal_count": 1,
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["click_count"], 12)
        self.assertEqual(result["wechat_add_count"], 5)
        self.assertEqual(result["cta_type"], "贷款失败原因分析")

    def test_can_record_conversion_events(self):
        tracker = FinanceConversionTracker()
        tracker.record({
            "id": 3,
            "title": "现金流文章",
            "category": "industry_law",
        })
        tracker.record_event(3, "cta_click", 2)
        tracker.record_event(3, "wechat_add", 1)
        tracker.record_event(3, "consult", 1)
        result = tracker.record_event(3, "deal", 1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["click_count"], 2)
        self.assertEqual(result["wechat_add_count"], 1)
        self.assertEqual(result["consult_count"], 1)
        self.assertEqual(result["deal_count"], 1)

    def test_cta_is_bound_to_conversion_goal_by_pain_point(self):
        expected = {
            "额度不足": "融资额度评估",
            "现金流紧张": "现金流健康检测",
            "征信问题": "征信优化诊断",
            "银行拒贷": "贷款失败原因分析",
        }
        for pain_point, conversion_goal in expected.items():
            with self.subTest(pain_point=pain_point):
                self.assertEqual(
                    match_finance_cta({"pain_point": pain_point})["title"],
                    conversion_goal,
                )


class FinanceLeadScoringAgentTestCase(unittest.TestCase):
    @staticmethod
    def _customer_for_level(level):
        if level == "S":
            return {
                "financing_need": "企业周转",
                "financing_purpose": "库存备货",
                "financing_amount": 2_000_000,
                "business_years": 5,
                "annual_revenue": 8_000_000,
                "operating_status": "稳定盈利",
                "documents_complete": True,
                "funding_days": 5,
                "credit_status": "良好无逾期",
            }
        if level == "A":
            return {
                "financing_need": "扩大经营",
                "financing_purpose": "设备采购",
                "business_years": 4,
                "annual_revenue": 2_000_000,
                "operating_status": "正常",
                "documents": ["营业执照", "流水", "财务报表", "纳税"],
                "funding_days": 20,
                "credit_status": "良好",
            }
        if level == "B":
            return {
                "financing_need": "现金流周转",
                "financing_purpose": "项目垫资",
                "business_years": 2,
                "annual_revenue": 1_500_000,
                "operating_status": "稳定",
                "documents": ["营业执照", "流水", "财务报表"],
                "urgency": "本月",
                "credit_status": "少量查询",
            }
        if level == "C":
            return {
                "financing_need": "想了解贷款",
                "business_years": 2,
                "annual_revenue": 1_200_000,
                "documents": ["营业执照", "流水", "财务报表"],
                "urgency": "未来考虑",
            }
        return {}

    def test_simulated_hundred_customers_cover_all_levels(self):
        customers = [
            self._customer_for_level(level)
            for level in ("S", "A", "B", "C", "D")
            for _ in range(20)
        ]

        results = [FinanceLeadScoringAgent.score(customer) for customer in customers]

        self.assertEqual(len(results), 100)
        self.assertEqual({item["level"] for item in results}, {"S", "A", "B", "C", "D"})
        for result in results:
            self.assertGreaterEqual(result["score"], 0)
            self.assertLessEqual(result["score"], 100)
            self.assertEqual(len(result["reason"]), 5)
            self.assertTrue(result["follow_action"])

    def test_customer_profile_tags_cover_five_finance_personas(self):
        samples = {
            "现金流困难型": "项目垫资导致现金流紧张",
            "额度不足型": "流水不少但授信额度不足",
            "征信优化型": "征信查询次数偏多",
            "贷款被拒型": "经营贷审批被拒",
            "融资规划型": "扩大生产前需要融资规划",
        }
        for expected, pain_point in samples.items():
            with self.subTest(expected=expected):
                result = FinanceLeadScoringAgent.score({"pain_point": pain_point})
                self.assertIn(expected, result["profile_tags"])

    def test_score_detail_uses_required_weights(self):
        result = FinanceLeadScoringAgent.score(self._customer_for_level("S"))
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["score_detail"], {
            "financing_need": 30,
            "enterprise_quality": 25,
            "data_completeness": 20,
            "urgency": 15,
            "credit": 10,
        })


if __name__ == "__main__":
    unittest.main()
