import unittest

from services.finance_content_analysis_agent import FinanceContentAnalysisAgent
from services.finance_content_growth_analyzer import (
    ContentGrowthScore,
    FinanceContentGrowthAnalyzer,
)
from services.article_growth_analyzer import ArticleGrowthAnalyzer
from services.finance_title_optimizer import FinanceTitleOptimizer


def build_articles():
    pains = (
        "银行拒贷",
        "现金流紧张",
        "额度不足",
        "征信问题",
        "负债过高",
        "续贷困难",
        "经营贷申请",
        "企业扩张资金不足",
        "融资成本过高",
        "贷款申请频繁失败",
    )
    rows = []
    for index, pain_point in enumerate(pains, start=1):
        reads = max(40, 1100 - index * 95)
        rows.append({
            "id": index,
            "title": f"企业老板申请经营贷遇到{pain_point}，为什么银行仍卡住？先查这3项",
            "category": "industry_law",
            "pain_point": pain_point,
            "scenario": "申请经营贷",
            "target_customer": "经营3年以上老板",
            "title_score": 100 if index <= 5 else 70,
            "view_count": reads,
            "like_count": max(0, 100 - index * 10),
            "comment_count": max(0, 20 - index * 2),
            "consult_count": max(0, 20 - index * 2),
            "deal_count": max(0, 7 - index),
        })
    return rows


class FinanceContentGrowthAnalysisTests(unittest.TestCase):
    def test_ten_articles_receive_weighted_growth_scores(self):
        articles = build_articles()
        analysis = FinanceContentGrowthAnalyzer.analyze_articles(articles)

        self.assertEqual(len(analysis["articles"]), 10)
        self.assertEqual(analysis["summary"]["total_articles"], 10)
        self.assertGreaterEqual(analysis["articles"][0]["growth_score"], 80)
        self.assertEqual(analysis["articles"][0]["growth_level"], "high_growth")
        self.assertEqual(analysis["articles"][-1]["growth_level"], "low_growth")
        for article in analysis["articles"]:
            self.assertLessEqual(article["growth_score"], 100)
            self.assertAlmostEqual(
                article["growth_score"],
                round(
                    article["traffic_score"]
                    + article["interaction_score"]
                    + article["acquisition_score"],
                    2,
                ),
            )
            for field in (
                "article_id",
                "title",
                "pain_point",
                "scenario",
                "target_customer",
                "title_score",
                "read_count",
                "like_count",
                "comment_count",
                "consult_count",
                "conversion_count",
            ):
                self.assertIn(field, article)

    def test_score_weights_and_levels(self):
        self.assertEqual(ContentGrowthScore.level(80), "high_growth")
        self.assertEqual(ContentGrowthScore.level(50), "medium_growth")
        self.assertEqual(ContentGrowthScore.level(49.99), "low_growth")
        scored = ContentGrowthScore.calculate(
            {
                "read_count": 100,
                "like_count": 10,
                "comment_count": 5,
                "consult_count": 3,
                "conversion_count": 1,
            },
            {
                "max_reads": 100,
                "max_interaction_rate": 0.2,
                "max_acquisition_rate": 0.05,
            },
        )
        self.assertEqual(scored["traffic_score"], 40)
        self.assertEqual(scored["interaction_score"], 30)
        self.assertEqual(scored["acquisition_score"], 30)
        self.assertEqual(scored["growth_score"], 100)

    def test_single_article_analysis_returns_required_output_fields(self):
        result = FinanceContentGrowthAnalyzer.analyze_article(build_articles()[0])

        self.assertTrue(result["ok"])
        self.assertIn("growth_score", result)
        self.assertIn(result["growth_level"], {"high_growth", "medium_growth", "low_growth"})
        for field in (
            "article_id", "title", "pain_point", "scenario", "target_customer",
            "title_score", "read_count", "like_count", "comment_count",
            "consult_count", "conversion_count",
        ):
            self.assertIn(field, result)
    def test_analysis_agent_explains_top_and_low_articles(self):
        growth = FinanceContentGrowthAnalyzer.analyze_articles(build_articles())
        insights = FinanceContentAnalysisAgent.analyze(growth)

        self.assertTrue(insights["top_articles"])
        self.assertTrue(insights["low_performance_articles"])
        self.assertTrue(insights["success_reasons"])
        self.assertTrue(insights["failure_reasons"])
        self.assertTrue(insights["replication_directions"])
        self.assertTrue(insights["optimization_suggestions"])
        self.assertTrue(insights["content_direction_advice"])

    def test_title_optimizer_returns_reason_and_score_change(self):
        article = {
            "article_id": 9,
            "title": "融资行业分析",
            "pain_point": "额度不足",
            "scenario": "设备采购",
            "target_customer": "年流水500万以上老板",
            "growth_level": "low_growth",
            "traffic_score": 10,
        }
        result = FinanceTitleOptimizer.optimize(article)

        self.assertEqual(result["original_title"], "融资行业分析")
        self.assertNotEqual(result["optimized_title"], result["original_title"])
        self.assertGreaterEqual(result["optimized_score"], 75)
        self.assertGreater(result["score_change"], 0)
        self.assertIn("增长表现偏低", result["reason"])

    def test_existing_growth_normalizer_preserves_industry_category(self):
        normalized = ArticleGrowthAnalyzer._normalize_dashboard_article({
            "id": 88,
            "title": "企业老板经营贷被拒",
            "category": "industry_law",
            "stored_title_score": 80,
            "stored_content_score": 80,
            "stored_growth_score": 80,
        })

        self.assertEqual(normalized["category"], "industry_law")
        self.assertEqual(normalized["article_type"], "industry_law")
        self.assertTrue(FinanceContentGrowthAnalyzer.is_industry_law(normalized))
    def test_non_industry_templates_are_excluded(self):
        articles = build_articles()
        articles.append({
            "id": 99,
            "title": "品牌宣传文章",
            "category": "brand",
            "view_count": 99999,
            "consult_count": 999,
        })

        analysis = FinanceContentGrowthAnalyzer.analyze_articles(articles)

        self.assertEqual(len(analysis["articles"]), 10)
        self.assertNotIn(99, [item["article_id"] for item in analysis["articles"]])

    def test_analysis_log_contains_score_and_recommendation(self):
        with self.assertLogs(
            "services.finance_content_growth_analyzer",
            level="INFO",
        ) as captured:
            FinanceContentGrowthAnalyzer.analyze_articles(build_articles()[:1])

        line = captured.output[-1]
        self.assertIn("[finance-growth-analysis]", line)
        self.assertIn("article_id=1", line)
        self.assertIn("score=", line)
        self.assertIn("recommendation=", line)


if __name__ == "__main__":
    unittest.main()
