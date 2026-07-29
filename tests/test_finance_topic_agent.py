import unittest

from services.enterprise_finance_content_library import (
    CUSTOMER_PROFILES,
    FINANCING_SCENARIOS,
    INDUSTRY_HOTSPOTS,
    OWNER_PAIN_POINTS,
    match_finance_cta,
)
from services.finance_topic_agent import (
    FinanceTopicAgent,
    FinanceTopicTitleScorer,
)


class FinanceTopicAgentTests(unittest.TestCase):
    def test_generates_ten_complete_qualified_topics(self):
        topics = FinanceTopicAgent.generate_topics()

        self.assertEqual(len(topics), 10)
        self.assertEqual(len({topic["title"] for topic in topics}), 10)
        for topic in topics:
            for key in (
                "title",
                "pain_point",
                "scenario",
                "target_customer",
                "conversion_goal",
                "score",
            ):
                self.assertTrue(topic.get(key), key)
            self.assertEqual(topic["article_type"], "industry_law")
            self.assertGreaterEqual(topic["score"], 75)
            self.assertNotIn("贷款行业的底层规律", topic["title"])
            self.assertNotIn("融资行业分析", topic["title"])

    def test_content_assets_have_required_values(self):
        self.assertEqual(len(OWNER_PAIN_POINTS), 10)
        self.assertEqual(len(FINANCING_SCENARIOS), 9)
        self.assertEqual(len(CUSTOMER_PROFILES), 6)
        self.assertGreaterEqual(len(INDUSTRY_HOTSPOTS), 1)
        self.assertIn("现金流紧张", OWNER_PAIN_POINTS)
        self.assertIn("申请经营贷", FINANCING_SCENARIOS)
        self.assertIn("年流水500万以上老板", CUSTOMER_PROFILES)

    def test_low_score_or_industry_big_word_title_is_regenerated(self):
        title, score = FinanceTopicAgent._ensure_qualified_title(
            "贷款行业的底层规律",
            "银行拒贷",
            "申请经营贷",
            "经营3年以上老板",
        )

        self.assertGreaterEqual(score, 75)
        self.assertNotIn("贷款行业的底层规律", title)
        self.assertTrue(FinanceTopicTitleScorer.score_title(title)["qualified"])

    def test_cta_matches_topic_pain(self):
        cases = {
            "现金流紧张": "现金流健康检测",
            "征信问题": "征信优化诊断",
            "额度不足": "融资额度评估",
            "银行拒贷": "贷款失败原因分析",
        }
        for pain_point, expected_title in cases.items():
            with self.subTest(pain_point=pain_point):
                cta = match_finance_cta({"pain_point": pain_point})
                self.assertEqual(cta["title"], expected_title)

    def test_log_records_topic_dimensions_and_article_id(self):
        topic = FinanceTopicAgent.generate_topics(limit=1)[0]
        with self.assertLogs("services.finance_topic_agent", level="INFO") as captured:
            FinanceTopicAgent.log_topic(topic, generated_article_id=987)

        line = captured.output[-1]
        self.assertIn("[finance-topic-agent]", line)
        self.assertIn("pain_point=", line)
        self.assertIn("scenario=", line)
        self.assertIn("title_score=", line)
        self.assertIn("generated_article_id=987", line)

if __name__ == "__main__":
    unittest.main()
