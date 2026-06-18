import sqlite3
import unittest
from unittest.mock import patch

from flask import render_template

from database import (
    MYSQL_CONTENT_GROWTH_CREATE_SQL,
    SQLITE_CONTENT_GROWTH_CREATE_SQL,
)
from services.article_growth_analyzer import ArticleGrowthAnalyzer
from services.title_score_service import TitleScoreService
from services.topic_engine import TopicEngine
from web_ui.app import app


class ContentGrowthDatabaseSqlTestCase(unittest.TestCase):
    def test_mysql_sql_does_not_use_legacy_reads_column(self):
        self.assertNotIn("reads INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertNotIn("likes INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)

    def test_mysql_sql_uses_canonical_metric_columns(self):
        self.assertIn("id INT AUTO_INCREMENT PRIMARY KEY", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertIn("view_count INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertIn("like_count INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)

    def test_sqlite_create_sql_executes(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(SQLITE_CONTENT_GROWTH_CREATE_SQL)
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(article_growth_metrics)").fetchall()
            }
        finally:
            conn.close()

        self.assertIn("view_count", columns)
        self.assertIn("growth_score", columns)


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

    def test_dashboard_structure_is_stable_when_database_fails(self):
        with patch.object(ArticleGrowthAnalyzer, "ensure_storage", return_value=False), patch.object(
            ArticleGrowthAnalyzer,
            "_fetch_dashboard_rows",
            side_effect=RuntimeError("db unavailable"),
        ):
            result = ArticleGrowthAnalyzer.get_dashboard_data()

        self.assertFalse(result["ok"])
        self.assertEqual(result["articles"], [])
        self.assertEqual(result["summary"], ArticleGrowthAnalyzer.SUMMARY_DEFAULTS)
        self.assertTrue(result["error"])

    def test_rewrite_uses_fallback_when_title_optimizer_fails(self):
        analysis = {
            "ok": True,
            "error": None,
            "title": "企业经营贷",
            "view_count": 10,
            "failure_reasons": ["阅读量偏低"],
            "title_score": {"optimized_titles": []},
        }
        with patch.object(ArticleGrowthAnalyzer, "analyze_article_growth", return_value=analysis), patch.object(
            TitleScoreService,
            "optimize_titles",
            side_effect=RuntimeError("AI unavailable"),
        ):
            result = ArticleGrowthAnalyzer.rewrite_for_growth(1)

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(len(result["new_titles"]), 3)

    def test_metric_compatibility_maps_reads_and_likes(self):
        metrics = ArticleGrowthAnalyzer._normalize_metrics({"reads": 12, "likes": 3})

        self.assertEqual(metrics["view_count"], 12)
        self.assertEqual(metrics["like_count"], 3)


class ContentGrowthRoutesTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"
            session["role_display"] = "管理员"

    def test_dashboard_empty_data_returns_200(self):
        empty = {
            "ok": True,
            "articles": [],
            "summary": dict(ArticleGrowthAnalyzer.SUMMARY_DEFAULTS),
            "topics": [],
            "error": None,
        }
        with patch.object(ArticleGrowthAnalyzer, "get_dashboard_data", return_value=empty):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("暂无文章增长数据", response.get_data(as_text=True))

    def test_dashboard_database_exception_returns_200(self):
        with patch.object(
            ArticleGrowthAnalyzer,
            "get_dashboard_data",
            side_effect=RuntimeError("database failed"),
        ):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("已自动降级展示", response.get_data(as_text=True))

    def test_dashboard_disabled_returns_200(self):
        with patch("web_ui.app.CONTENT_GROWTH_ENABLED", False):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("文章增长中心未启用", response.get_data(as_text=True))

    def test_missing_article_analyze_returns_json_not_500(self):
        response = self.client.post("/article/999999999/growth-analyze", json={})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertFalse(response.get_json()["ok"])

    def test_rewrite_route_exception_returns_fallback_json(self):
        with patch.object(
            ArticleGrowthAnalyzer,
            "rewrite_for_growth",
            side_effect=RuntimeError("AI failed"),
        ):
            response = self.client.post("/article/1/rewrite-for-growth", json={})

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(len(data["new_titles"]), 3)

    def test_template_renders_with_empty_articles_and_summary(self):
        with app.test_request_context("/content-growth/dashboard"):
            html = render_template(
                "content_growth_dashboard.html",
                articles=[],
                summary={},
                topics=[],
                error=None,
                growth_enabled=True,
                low_traffic_threshold=300,
            )

        self.assertIn("暂无文章增长数据", html)
        self.assertIn("总阅读量", html)

    def test_system_health_always_returns_json(self):
        response = self.client.get("/system/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertIn("errors", response.get_json())

    def test_system_health_database_failure_still_returns_json(self):
        with patch("web_ui.app.get_db", side_effect=RuntimeError("db unavailable")), patch(
            "web_ui.app.init_content_growth_tables",
            return_value=False,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "get_dashboard_data",
            return_value=ArticleGrowthAnalyzer._dashboard_result(),
        ):
            response = self.client.get("/system/health")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(data["db"], "error")


if __name__ == "__main__":
    unittest.main()
