import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from flask import render_template

from config import CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD
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
        article = {"id": 1, "title": "企业经营贷", "content": "原始正文"}
        with patch.object(ArticleGrowthAnalyzer, "analyze_article_growth", return_value=analysis), patch.object(
            TitleScoreService,
            "optimize_titles",
            side_effect=RuntimeError("AI unavailable"),
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_get_article",
            return_value=article,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_save_rewrite_proposal",
            return_value=True,
        ):
            result = ArticleGrowthAnalyzer.rewrite_for_growth(1)

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(len(result["new_titles"]), 3)
        self.assertEqual(article["content"], "原始正文")
        self.assertIn("optimized_content", result)

    def test_metric_compatibility_maps_reads_and_likes(self):
        metrics = ArticleGrowthAnalyzer._normalize_metrics({"reads": 12, "likes": 3})

        self.assertEqual(metrics["view_count"], 12)
        self.assertEqual(metrics["like_count"], 3)

    def test_draft_sent_has_clear_chinese_status(self):
        self.assertEqual(
            ArticleGrowthAnalyzer._status_label("draft_sent"),
            "已推送草稿箱，未确认发布",
        )

    def test_new_account_low_traffic_threshold_defaults_to_50(self):
        self.assertEqual(CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD, 50)

    def test_growth_dashboard_template_does_not_hardcode_300(self):
        template_path = Path(__file__).resolve().parents[1] / "web_ui" / "templates" / "content_growth_dashboard.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertNotIn("default(300", template)
        self.assertIn("default(50", template)


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

    def test_manual_metrics_update_endpoint(self):
        expected = {
            "ok": True,
            "article_id": 12,
            "metrics": {"view_count": 88, "deal_count": 2},
            "growth_score": 76,
        }
        with patch.object(ArticleGrowthAnalyzer, "update_metrics", return_value=expected) as update:
            response = self.client.post(
                "/article/12/growth-metrics/update",
                json={"view_count": 88, "deal_count": 2},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        update.assert_called_once_with(12, {"view_count": 88, "deal_count": 2})

    def test_rewrite_generation_does_not_overwrite_original_article(self):
        original = {"id": 3, "title": "原始标题", "content": "原始正文", "status": "published"}
        analysis = {
            "ok": True,
            "title": original["title"],
            "view_count": 10,
            "failure_reasons": ["标题点击弱"],
            "title_score": {"optimized_titles": ["优化标题"]},
        }
        with patch.object(ArticleGrowthAnalyzer, "_get_article", return_value=original), patch.object(
            ArticleGrowthAnalyzer,
            "analyze_article_growth",
            return_value=analysis,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_save_rewrite_proposal",
            return_value=True,
        ):
            result = ArticleGrowthAnalyzer.rewrite_for_growth(3)

        self.assertTrue(result["ok"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["is_published"])
        self.assertEqual(result["available_actions"], ["create_new_draft"])
        self.assertEqual(result["original_title"], "原始标题")
        self.assertEqual(original["content"], "原始正文")

    def test_recommended_topic_generate_article_endpoint(self):
        generated = {
            "ok": True,
            "title": "老板经营贷被拒，先查这3点",
            "markdown": "正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>正文</p>",
        }
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated) as generate, patch(
            "web_ui.app.TemplateService.create_agent_article",
            return_value={"ok": True, "article_id": 321},
        ) as save:
            response = self.client.post(
                "/content-growth/topic/generate",
                json={"suggested_title": "老板经营贷被拒，先查这3点"},
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["article_id"], 321)
        generate.assert_called_once()
        save.assert_called_once()

    def test_create_draft_endpoint_returns_new_article(self):
        result = {
            "ok": True,
            "success": True,
            "new_article_id": 456,
            "redirect_url": "/article/456",
        }
        with patch.object(ArticleGrowthAnalyzer, "create_optimized_draft", return_value=result):
            response = self.client.post("/article/10/growth-rewrite/create-draft", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["new_article_id"], 456)

    def test_apply_endpoint_rejects_published_article(self):
        result = {
            "ok": False,
            "success": False,
            "error": "已发表文章不能直接覆盖，请生成优化版新草稿",
        }
        with patch.object(ArticleGrowthAnalyzer, "apply_optimized_to_draft", return_value=result):
            response = self.client.post("/article/10/growth-rewrite/apply", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assertIn("不能直接覆盖", response.get_json()["error"])

    def test_template_renders_with_empty_articles_and_summary(self):
        with app.test_request_context("/content-growth/dashboard"):
            html = render_template(
                "content_growth_dashboard.html",
                articles=[],
                summary={},
                topics=[],
                error=None,
                growth_enabled=True,
                low_traffic_threshold=50,
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


class ContentGrowthRewriteIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source_name TEXT,
                source_url TEXT,
                tags TEXT,
                status TEXT DEFAULT 'draft',
                review_status TEXT DEFAULT 'draft',
                publish_status TEXT DEFAULT 'not_ready',
                is_original INTEGER DEFAULT 0,
                html_content TEXT,
                source_article_id INTEGER,
                created_at DATETIME DEFAULT (datetime('now','localtime')),
                updated_at DATETIME DEFAULT (datetime('now','localtime'))
            );
            """
        )
        conn.execute(SQLITE_CONTENT_GROWTH_CREATE_SQL)
        conn.execute(
            "INSERT INTO articles (title, content, status) VALUES (?,?,?)",
            ("已发表原文", "原始正文", "published"),
        )
        conn.execute(
            "INSERT INTO articles (title, content, status) VALUES (?,?,?)",
            ("草稿原文", "草稿正文", "draft"),
        )
        for article_id, optimized_title in ((1, "已发表优化标题"), (2, "草稿优化标题")):
            conn.execute(
                """
                INSERT INTO article_growth_metrics
                (article_id, rewrite_titles, rewrite_intro, rewrite_outline,
                 rewrite_cta, optimized_content, growth_reason)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    article_id,
                    f'["{optimized_title}"]',
                    "优化开头",
                    '["结构一", "结构二"]',
                    "优化 CTA",
                    "优化后的完整正文",
                    "阅读量偏低",
                ),
            )
        conn.commit()
        conn.close()

        def connection_factory():
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        self.connection_factory = connection_factory
        self.db_patch = patch(
            "services.article_growth_analyzer.get_db",
            side_effect=self.connection_factory,
        )
        self.storage_patch = patch.object(
            ArticleGrowthAnalyzer,
            "ensure_storage",
            return_value=True,
        )
        self.db_patch.start()
        self.storage_patch.start()

    def tearDown(self):
        self.storage_patch.stop()
        self.db_patch.stop()
        try:
            os.remove(self.db_path)
        except PermissionError:
            pass

    def test_published_create_draft_generates_new_linked_article(self):
        result = ArticleGrowthAnalyzer.create_optimized_draft(1)

        self.assertTrue(result["ok"])
        conn = self.connection_factory()
        try:
            source = conn.execute("SELECT title, content FROM articles WHERE id=1").fetchone()
            new_article = conn.execute(
                "SELECT title, content, status, source_article_id FROM articles WHERE id=?",
                (result["new_article_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(source["content"], "原始正文")
        self.assertEqual(new_article["status"], "draft")
        self.assertEqual(new_article["source_article_id"], 1)
        self.assertEqual(new_article["title"], "已发表优化标题")

    def test_draft_apply_updates_current_article(self):
        result = ArticleGrowthAnalyzer.apply_optimized_to_draft(2)

        self.assertTrue(result["ok"])
        conn = self.connection_factory()
        try:
            article = conn.execute("SELECT title, content FROM articles WHERE id=2").fetchone()
        finally:
            conn.close()
        self.assertEqual(article["title"], "草稿优化标题")
        self.assertEqual(article["content"], "优化后的完整正文")

    def test_published_apply_returns_error(self):
        result = ArticleGrowthAnalyzer.apply_optimized_to_draft(1)

        self.assertFalse(result["ok"])
        self.assertIn("不能直接覆盖", result["error"])

    def test_manual_metrics_are_read_by_dashboard(self):
        update = ArticleGrowthAnalyzer.update_metrics(
            2,
            {
                "read_count": 125,
                "like_count": 8,
                "share_count": 3,
                "favorite_count": 2,
                "comment_count": 1,
                "scan_count": 4,
                "consult_count": 2,
                "deal_count": 1,
            },
        )
        dashboard = ArticleGrowthAnalyzer.get_dashboard_data()
        article = next(item for item in dashboard["articles"] if item["id"] == 2)

        self.assertTrue(update["ok"])
        self.assertEqual(article["view_count"], 125)
        self.assertEqual(article["deal_count"], 1)
        self.assertTrue(article["has_metrics"])


if __name__ == "__main__":
    unittest.main()
