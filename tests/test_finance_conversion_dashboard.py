import unittest
from unittest.mock import patch

from services.article_growth_analyzer import ArticleGrowthAnalyzer
from web_ui.app import app


class FinanceConversionDashboardTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"

    def test_dashboard_exposes_phase4_conversion_center(self):
        articles = [
            {
                "id": index + 1,
                "title": f"企业老板融资场景文章{index + 1}",
                "category": "industry_law",
                "conversion_goal": "融资额度评估",
                "view_count": 3000 - index * 80,
                "click_count": 180 - index * 4,
                "wechat_add_count": 90 - index * 2,
                "consult_count": 50 - index,
                "deal_count": max(0, 12 - index // 2),
            }
            for index in range(20)
        ]
        articles.append({
            "id": 999,
            "title": "普通品牌宣传文章",
            "category": "brand",
            "view_count": 999999,
            "deal_count": 999,
        })
        dashboard = {
            "ok": True,
            "articles": articles,
            "summary": dict(ArticleGrowthAnalyzer.SUMMARY_DEFAULTS),
            "topics": [],
            "error": None,
        }

        with patch.object(ArticleGrowthAnalyzer, "get_dashboard_data", return_value=dashboard):
            html_response = self.client.get("/content-growth/dashboard")
            json_response = self.client.get("/content-growth/dashboard?format=json")

        html = html_response.get_data(as_text=True)
        data = json_response.get_json()["finance_conversion"]
        self.assertEqual(html_response.status_code, 200)
        for label in ("融资内容转化中心", "文章获客排行", "客户漏斗", "高价值内容推荐"):
            self.assertIn(label, html)
        self.assertEqual(data["summary"]["total_articles"], 20)
        self.assertNotIn(999, [item["article_id"] for item in data["records"]])
        self.assertTrue(data["ranking"])
        self.assertTrue(data["recommendations"])


if __name__ == "__main__":
    unittest.main()
