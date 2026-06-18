import unittest

from services.article_growth_analyzer import ArticleGrowthAnalyzer
from services.title_score_service import TitleScoreService
from services.topic_engine import TopicEngine


class ContentGrowthServicesTestCase(unittest.TestCase):
    def test_topic_engine_returns_required_fields(self):
        topics = TopicEngine.generate_topics()

        self.assertEqual(len(topics), 8)
        for topic in topics:
            self.assertIn("target_customer", topic)
            self.assertIn("pain_point", topic)
            self.assertIn("article_angle", topic)
            self.assertIn("suggested_title", topic)
            self.assertIn("conversion_goal", topic)

    def test_low_title_score_generates_optimized_titles(self):
        result = TitleScoreService.score_title("融资知识科普")

        self.assertLess(result["score"], 80)
        self.assertEqual(len(result["optimized_titles"]), 5)

    def test_strong_title_scores_better_than_science_title(self):
        weak = TitleScoreService.score_title("融资知识科普")
        strong = TitleScoreService.score_title("老板经营贷被拒，先查这3点")

        self.assertGreater(strong["score"], weak["score"])

    def test_rewrite_payload_has_safe_defaults(self):
        payload = ArticleGrowthAnalyzer._normalize_metrics({})

        self.assertEqual(payload["reads"], 0)
        self.assertEqual(payload["consultations"], 0)
        self.assertEqual(len(ArticleGrowthAnalyzer._new_structure()), 7)
        self.assertIn("融资体检", ArticleGrowthAnalyzer._new_cta())


if __name__ == "__main__":
    unittest.main()
