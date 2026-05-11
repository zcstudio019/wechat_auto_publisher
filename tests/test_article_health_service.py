import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from services.article_health_service import ArticleHealthService


class ArticleHealthServiceTestCase(unittest.TestCase):
    """文章 AI 健康度服务测试。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "article_health_test.db")
        self.article_id = 1
        self._create_schema()
        self._insert_article()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _patch_db(self):
        return patch.multiple(
            "services.article_health_service",
            get_db=self._connect,
            is_mysql=lambda: False,
        )

    def _create_schema(self):
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ai_operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                action_type TEXT,
                ok INTEGER,
                result_json TEXT,
                created_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE publish_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                status TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        conn.commit()
        conn.close()

    def _insert_article(self, article_id=None, title="测试文章", status="draft"):
        safe_article_id = article_id or self.article_id
        conn = self._connect()
        conn.execute("INSERT INTO articles (id, title, status) VALUES (?, ?, ?)", (safe_article_id, title, status))
        conn.commit()
        conn.close()

    def _insert_log(self, action_type, result, hours_ago=0, article_id=None):
        safe_article_id = article_id or self.article_id
        created_at = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO ai_operation_logs (article_id, action_type, ok, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (safe_article_id, action_type, 1 if result.get("ok", True) else 0, json.dumps(result, ensure_ascii=False), created_at),
        )
        conn.commit()
        conn.close()

    def _insert_publish_task(self, status, article_id=None):
        safe_article_id = article_id or self.article_id
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO publish_tasks (article_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (safe_article_id, status, now_text, now_text),
        )
        conn.commit()
        conn.close()

    def _build_health(self):
        with self._patch_db():
            return ArticleHealthService.build_article_health(self.article_id)

    def _build_trend(self):
        with self._patch_db():
            return ArticleHealthService.build_health_trend(self.article_id)

    def test_score_normal_calculation(self):
        """无异常信号时健康分应为 100。"""
        health = self._build_health()
        self.assertEqual(health["score"], 100)
        self.assertEqual(health["risk_level"], "low")
        self.assertEqual(health["status"], "healthy")

    def test_high_risk_review_deducts_score(self):
        """最近 AI 审核 high risk 应扣分并提示人工关注。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        health = self._build_health()
        self.assertEqual(health["score"], 70)
        self.assertIn("AI审核高风险", health["signals"])
        self.assertTrue(health["need_manual_attention"])

    def test_preflight_failed_deducts_score(self):
        """最近终检未通过应扣分并提示人工关注。"""
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        health = self._build_health()
        self.assertEqual(health["score"], 75)
        self.assertIn("AI终检未通过", health["signals"])
        self.assertTrue(health["need_manual_attention"])

    def test_publish_failed_deducts_score(self):
        """最近发布任务失败应同时扣最近失败与失败任务风险。"""
        self._insert_publish_task("failed")
        health = self._build_health()
        self.assertEqual(health["score"], 65)
        self.assertIn("最近发布失败", health["signals"])
        self.assertIn("存在失败发布任务", health["signals"])
        self.assertTrue(health["need_manual_attention"])

    def test_workflow_high_risk_deducts_score(self):
        """最近工作流 high risk 应扣分并返回信号。"""
        self._insert_log("ai_workflow", {"ok": True, "workflow_status": "completed", "overall_risk": "high"})
        health = self._build_health()
        self.assertEqual(health["score"], 80)
        self.assertIn("工作流高风险", health["signals"])

    def test_rewrite_frequent_deducts_score(self):
        """最近 24 小时 AI 优化超过 3 次应扣分。"""
        for _ in range(4):
            self._insert_log("ai_rewrite", {"ok": True, "rewritten_title": "优化标题"})
        health = self._build_health()
        self.assertEqual(health["score"], 90)
        self.assertIn("AI重写次数较多", health["signals"])

    def test_workflow_frequent_deducts_score(self):
        """最近 24 小时 AI 工作流超过 5 次应扣分。"""
        for _ in range(6):
            self._insert_log("ai_workflow", {"ok": True, "workflow_status": "completed", "overall_risk": "low"})
        health = self._build_health()
        self.assertEqual(health["score"], 90)
        self.assertIn("AI工作流运行频繁", health["signals"])

    def test_risk_level_mapping(self):
        """分数应正确映射风险等级。"""
        self.assertEqual(ArticleHealthService._risk_level(80), "low")
        self.assertEqual(ArticleHealthService._risk_level(50), "medium")
        self.assertEqual(ArticleHealthService._risk_level(49), "high")

    def test_status_mapping(self):
        """分数应正确映射健康状态。"""
        self.assertEqual(ArticleHealthService._status(80), "healthy")
        self.assertEqual(ArticleHealthService._status(50), "warning")
        self.assertEqual(ArticleHealthService._status(49), "dangerous")

    def test_ai_activity_level_mapping(self):
        """最近 24 小时 AI 操作次数应正确映射活跃度。"""
        self.assertEqual(ArticleHealthService._activity_level(2), "low")
        self.assertEqual(ArticleHealthService._activity_level(3), "medium")
        self.assertEqual(ArticleHealthService._activity_level(7), "high")

    def test_need_manual_attention_for_high_score_risk(self):
        """多个风险叠加导致 high risk 时应提示人工关注。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "high"})
        self._insert_publish_task("failed")
        health = self._build_health()
        self.assertEqual(health["risk_level"], "high")
        self.assertEqual(health["status"], "dangerous")
        self.assertTrue(health["need_manual_attention"])

    def test_trend_score_change_calculation(self):
        """趋势应基于最近操作前后健康分计算 score_change。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        self._insert_log("ai_review", {"ok": True, "risk_level": "low", "can_publish": True})
        trend = self._build_trend()
        self.assertEqual(trend["recent_scores"], [70, 100])
        self.assertEqual(trend["score_change"], 30)

    def test_trend_direction_up(self):
        """健康分提升 15 分及以上应判定为 up。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        self._insert_log("ai_review", {"ok": True, "risk_level": "low", "can_publish": True})
        trend = self._build_trend()
        self.assertEqual(trend["trend_direction"], "up")
        self.assertEqual(trend["trend_level"], "good")

    def test_trend_direction_stable(self):
        """健康分变化不足 15 分应判定为 stable。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "low", "can_publish": True})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": True, "risk_level": "low"})
        trend = self._build_trend()
        self.assertEqual(trend["trend_direction"], "stable")
        self.assertEqual(trend["trend_level"], "normal")

    def test_trend_direction_down(self):
        """健康分下降 15 分及以上应判定为 down。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "low", "can_publish": True})
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        trend = self._build_trend()
        self.assertEqual(trend["trend_direction"], "down")
        self.assertEqual(trend["trend_level"], "danger")

    def test_trend_level_mapping(self):
        """趋势方向应正确映射趋势级别。"""
        self.assertEqual(ArticleHealthService._trend_level("up"), "good")
        self.assertEqual(ArticleHealthService._trend_level("stable"), "normal")
        self.assertEqual(ArticleHealthService._trend_level("down"), "danger")

    def test_trend_summary_mapping(self):
        """趋势摘要应根据方向自动生成。"""
        self.assertIn("持续提升", ArticleHealthService._trend_summary("up"))
        self.assertIn("整体稳定", ArticleHealthService._trend_summary("stable"))
        self.assertIn("风险正在升高", ArticleHealthService._trend_summary("down"))

    def test_trend_recent_scores_returned(self):
        """趋势结果应返回最近阶段分数轨迹。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "high", "can_publish": False})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "high"})
        trend = self._build_trend()
        self.assertEqual(len(trend["recent_scores"]), 2)
        self.assertTrue(all(isinstance(score, int) for score in trend["recent_scores"]))

    def test_trend_signals_limit(self):
        """趋势 signals 最多返回 4 条。"""
        trend = ArticleHealthService._build_trend_result(
            [50, 80],
            ["信号1", "信号2", "信号3", "信号4", "信号5"],
        )
        self.assertEqual(len(trend["signals"]), 4)

    def test_trend_empty_logs_fallback(self):
        """没有 AI 日志时趋势应安全兜底。"""
        trend = self._build_trend()
        self.assertEqual(trend["recent_scores"], [])
        self.assertEqual(trend["score_change"], 0)
        self.assertEqual(trend["trend_direction"], "stable")

    def test_trend_single_log_fallback(self):
        """只有单条 AI 日志时趋势应返回单点轨迹并保持稳定。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "low", "can_publish": True})
        trend = self._build_trend()
        self.assertEqual(trend["recent_scores"], [100])
        self.assertEqual(trend["score_change"], 0)
        self.assertEqual(trend["trend_direction"], "stable")

    def test_health_overview_empty_article_ids(self):
        """空 article_ids 应返回空字典。"""
        self.assertEqual(ArticleHealthService.build_articles_health_overview([]), {})

    def test_health_overview_multiple_articles(self):
        """多文章应返回以 article_id 为 key 的概览字典。"""
        with patch.object(ArticleHealthService, "build_article_health") as mock_health, \
             patch.object(ArticleHealthService, "build_health_trend") as mock_trend:
            mock_health.side_effect = lambda article_id: {
                "score": 80 + article_id,
                "risk_level": "low",
                "status": "healthy",
                "need_manual_attention": False,
                "signals": [],
            }
            mock_trend.side_effect = lambda article_id: {
                "trend_direction": "stable",
                "score_change": article_id,
                "signals": [],
            }

            overview = ArticleHealthService.build_articles_health_overview([1, 2])

        self.assertEqual(set(overview.keys()), {1, 2})
        self.assertEqual(overview[1]["score"], 81)
        self.assertEqual(overview[2]["score_change"], 2)

    def test_health_overview_single_failure_does_not_affect_others(self):
        """单篇异常应兜底，不影响其他文章概览。"""
        def fake_health(article_id):
            if article_id == 1:
                raise RuntimeError("health failed")
            return {
                "score": 88,
                "risk_level": "low",
                "status": "healthy",
                "need_manual_attention": False,
                "signals": ["正常"],
            }

        with patch.object(ArticleHealthService, "build_article_health", side_effect=fake_health), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={
                 "trend_direction": "up",
                 "score_change": 20,
                 "signals": ["趋势上升"],
             }):
            overview = ArticleHealthService.build_articles_health_overview([1, 2])

        self.assertEqual(overview[1]["risk_level"], "unknown")
        self.assertEqual(overview[1]["signals"], ["健康分析失败"])
        self.assertEqual(overview[2]["score"], 88)
        self.assertEqual(overview[2]["trend_direction"], "up")

    def test_health_overview_signals_limit_two(self):
        """列表页概览 signals 最多返回 2 条。"""
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 60,
            "risk_level": "medium",
            "status": "warning",
            "need_manual_attention": True,
            "signals": ["信号1", "信号2"],
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "trend_direction": "down",
            "score_change": -20,
            "signals": ["信号3", "信号4"],
        }):
            overview = ArticleHealthService.build_articles_health_overview([1])

        self.assertEqual(len(overview[1]["signals"]), 2)
        self.assertEqual(overview[1]["signals"], ["信号1", "信号2"])

    def test_health_overview_fallback_unknown_structure(self):
        """健康分析失败时应返回 unknown 兜底结构。"""
        fallback = ArticleHealthService._fallback_overview()
        self.assertEqual(fallback["score"], 0)
        self.assertEqual(fallback["risk_level"], "unknown")
        self.assertEqual(fallback["status"], "unknown")
        self.assertFalse(fallback["need_manual_attention"])
        self.assertEqual(fallback["trend_direction"], "stable")
        self.assertEqual(fallback["score_change"], 0)
        self.assertEqual(fallback["signals"], ["健康分析失败"])

    def test_health_overview_trend_direction_pass_through(self):
        """概览应透传趋势方向。"""
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 92,
            "risk_level": "low",
            "status": "healthy",
            "need_manual_attention": False,
            "signals": [],
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "trend_direction": "down",
            "score_change": -18,
            "signals": [],
        }):
            overview = ArticleHealthService.build_articles_health_overview([1])

        self.assertEqual(overview[1]["trend_direction"], "down")

    def test_health_overview_score_change_pass_through(self):
        """概览应透传 score_change。"""
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 92,
            "risk_level": "low",
            "status": "healthy",
            "need_manual_attention": False,
            "signals": [],
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "trend_direction": "up",
            "score_change": 22,
            "signals": [],
        }):
            overview = ArticleHealthService.build_articles_health_overview([1])

        self.assertEqual(overview[1]["score_change"], 22)

    def test_ai_risk_dashboard_structure(self):
        """Dashboard 应返回固定结构。"""
        with self._patch_db():
            dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertIn("summary", dashboard)
        self.assertIn("top_risk_articles", dashboard)
        self.assertIn("top_active_articles", dashboard)
        self.assertIn("recent_fail_articles", dashboard)
        self.assertIn("trend_summary", dashboard)

    def test_ai_risk_dashboard_avg_health_score(self):
        """Dashboard 平均健康分应正确计算。"""
        self._insert_article(2, "低风险文章")
        with patch.object(ArticleHealthService, "build_article_health") as mock_health, \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            mock_health.side_effect = [
                {"score": 60, "risk_level": "medium", "status": "warning", "need_manual_attention": False},
                {"score": 100, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            ]
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertEqual(dashboard["summary"]["avg_health_score"], 80)

    def test_ai_risk_dashboard_top_risk_articles_sorted(self):
        """高风险文章应按风险等级和健康分升序排序。"""
        self._insert_article(2, "中风险")
        self._insert_article(3, "高风险低分")
        fake_health = {
            1: {"score": 90, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 60, "risk_level": "medium", "status": "warning", "need_manual_attention": False},
            3: {"score": 30, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: fake_health[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertEqual([item["article_id"] for item in dashboard["top_risk_articles"][:3]], [3, 2, 1])

    def test_ai_risk_dashboard_top_active_articles(self):
        """Dashboard 应统计最近 24 小时 AI 操作活跃文章。"""
        self._insert_article(2, "活跃文章")
        self._insert_log("ai_review", {"ok": True}, article_id=2)
        self._insert_log("ai_rewrite", {"ok": True}, article_id=2)
        self._insert_log("ai_review", {"ok": True}, article_id=1, hours_ago=30)
        with self._patch_db():
            active_articles = ArticleHealthService._build_top_active_articles([
                {"id": 1, "title": "旧文章"},
                {"id": 2, "title": "活跃文章"},
            ])

        self.assertEqual(active_articles[0]["article_id"], 2)
        self.assertEqual(active_articles[0]["ai_operation_count"], 2)

    def test_ai_risk_dashboard_recent_fail_articles(self):
        """Dashboard 应统计发布失败文章。"""
        self._insert_article(2, "失败文章")
        self._insert_publish_task("failed", article_id=2)
        self._insert_publish_task("failed", article_id=2)
        self._insert_publish_task("success", article_id=1)
        with self._patch_db():
            fail_articles = ArticleHealthService._build_recent_fail_articles([
                {"id": 1, "title": "成功文章"},
                {"id": 2, "title": "失败文章"},
            ])

        self.assertEqual(fail_articles[0]["article_id"], 2)
        self.assertEqual(fail_articles[0]["failed_count"], 2)

    def test_ai_risk_dashboard_trend_summary(self):
        """Dashboard 应统计 up/stable/down 趋势数量。"""
        self._insert_article(2, "稳定文章")
        self._insert_article(3, "下降文章")
        trend_map = {
            1: {"trend_direction": "up"},
            2: {"trend_direction": "stable"},
            3: {"trend_direction": "down"},
        }
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 80,
            "risk_level": "low",
            "status": "healthy",
            "need_manual_attention": False,
        }), patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map[article_id]):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertEqual(dashboard["trend_summary"]["up_count"], 1)
        self.assertEqual(dashboard["trend_summary"]["stable_count"], 1)
        self.assertEqual(dashboard["trend_summary"]["down_count"], 1)

    def test_ai_risk_dashboard_missing_title_fallback(self):
        """标题缺失时应显示未知文章。"""
        conn = self._connect()
        conn.execute("UPDATE articles SET title=NULL WHERE id=?", (self.article_id,))
        conn.commit()
        conn.close()
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 80,
            "risk_level": "low",
            "status": "healthy",
            "need_manual_attention": False,
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertEqual(dashboard["top_risk_articles"][0]["title"], "未知文章")

    def test_ai_risk_dashboard_empty_data(self):
        """无文章时 Dashboard 应安全兜底。"""
        conn = self._connect()
        conn.execute("DELETE FROM articles")
        conn.commit()
        conn.close()
        with self._patch_db():
            dashboard = ArticleHealthService.build_ai_risk_dashboard()

        self.assertEqual(dashboard["summary"]["total_articles"], 0)
        self.assertEqual(dashboard["summary"]["avg_health_score"], 0)
        self.assertEqual(dashboard["top_risk_articles"], [])

    def test_ai_risk_dashboard_filter_by_risk_level(self):
        """Dashboard 应支持按风险等级筛选。"""
        self._insert_article(2, "高风险文章")
        health_map = {
            1: {"score": 90, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 30, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(risk_level="high")

        self.assertEqual([item["article_id"] for item in dashboard["filtered_articles"]], [2])
        self.assertEqual(dashboard["filters"]["risk_level"], "high")

    def test_ai_risk_dashboard_filter_by_need_attention(self):
        """Dashboard 应支持只看需人工关注文章。"""
        self._insert_article(2, "需关注文章")
        health_map = {
            1: {"score": 90, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 45, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(need_attention=True)

        self.assertEqual([item["article_id"] for item in dashboard["filtered_articles"]], [2])
        self.assertTrue(dashboard["filters"]["need_attention"])

    def test_ai_risk_dashboard_filter_by_trend_direction(self):
        """Dashboard 应支持按趋势方向筛选。"""
        self._insert_article(2, "下降文章")
        trend_map = {1: {"trend_direction": "up"}, 2: {"trend_direction": "down"}}
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 80,
            "risk_level": "low",
            "status": "healthy",
            "need_manual_attention": False,
        }), patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map[article_id]):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(trend_direction="down")

        self.assertEqual([item["article_id"] for item in dashboard["filtered_articles"]], [2])

    def test_ai_risk_dashboard_filter_by_max_score(self):
        """Dashboard 应支持按最大健康分筛选。"""
        self._insert_article(2, "低分文章")
        health_map = {
            1: {"score": 90, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 55, "risk_level": "medium", "status": "warning", "need_manual_attention": False},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(max_score=60)

        self.assertEqual([item["article_id"] for item in dashboard["filtered_articles"]], [2])

    def test_ai_risk_dashboard_filter_combined_conditions(self):
        """Dashboard 应支持多条件组合筛选。"""
        self._insert_article(2, "高风险下降")
        self._insert_article(3, "高风险稳定")
        health_map = {
            1: {"score": 90, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 35, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
            3: {"score": 40, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
        }
        trend_map = {
            1: {"trend_direction": "up"},
            2: {"trend_direction": "down"},
            3: {"trend_direction": "stable"},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map[article_id]):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(
                    risk_level="high",
                    need_attention=True,
                    trend_direction="down",
                    max_score=60,
                )

        self.assertEqual([item["article_id"] for item in dashboard["filtered_articles"]], [2])

    def test_ai_dashboard_route_ignores_invalid_max_score(self):
        """路由遇到非法 max_score 应忽略并传 None 给 service。"""
        from web_ui.app import app

        captured = {}

        def fake_build_dashboard(**kwargs):
            captured.update(kwargs)
            return ArticleHealthService._empty_dashboard()

        with patch("web_ui.app.ArticleHealthService.build_ai_risk_dashboard", side_effect=fake_build_dashboard):
            app.config["TESTING"] = True
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard?max_score=abc")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(captured["max_score"])

    def test_ai_risk_dashboard_filtered_articles_limit_100(self):
        """filtered_articles 最多返回 100 条。"""
        articles = [{"id": index, "title": f"文章{index}"} for index in range(1, 106)]
        with patch.object(ArticleHealthService, "_list_articles_for_dashboard", return_value=articles), \
             patch.object(ArticleHealthService, "build_article_health", return_value={
                 "score": 30,
                 "risk_level": "high",
                 "status": "dangerous",
                 "need_manual_attention": True,
             }), patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "down"}), \
             patch.object(ArticleHealthService, "_build_top_active_articles", return_value=[]), \
             patch.object(ArticleHealthService, "_build_recent_fail_articles", return_value=[]):
            dashboard = ArticleHealthService.build_ai_risk_dashboard(risk_level="high")

        self.assertEqual(len(dashboard["filtered_articles"]), 100)

    def test_ai_risk_dashboard_summary_not_affected_by_filter(self):
        """summary 应保持全局统计，不受筛选条件影响。"""
        self._insert_article(2, "低分文章")
        health_map = {
            1: {"score": 100, "risk_level": "low", "status": "healthy", "need_manual_attention": False},
            2: {"score": 20, "risk_level": "high", "status": "dangerous", "need_manual_attention": True},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"trend_direction": "stable"}):
            with self._patch_db():
                dashboard = ArticleHealthService.build_ai_risk_dashboard(risk_level="high")

        self.assertEqual(dashboard["summary"]["total_articles"], 2)
        self.assertEqual(dashboard["summary"]["avg_health_score"], 60)
        self.assertEqual(len(dashboard["filtered_articles"]), 1)


if __name__ == "__main__":
    unittest.main()
