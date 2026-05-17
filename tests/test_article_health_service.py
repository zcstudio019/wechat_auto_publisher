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

        with patch("web_ui.app.ArticleHealthService.build_ai_risk_dashboard", side_effect=fake_build_dashboard), \
             patch("web_ui.app.ArticleHealthService.build_dashboard_snapshot_changes", return_value={
                 "last_snapshot_time": "",
                 "high_risk_change": 0,
                 "attention_change": 0,
                 "avg_score_change": 0,
             }), patch("web_ui.app.ArticleHealthService.write_ai_dashboard_snapshot"), \
             patch("web_ui.app.ArticleHealthService.append_ai_ops_score_history"), \
             patch("web_ui.app.ArticleHealthService.append_ai_ops_duty_history"), \
             patch("web_ui.app.ArticleHealthService.build_ai_ops_duty_history_summary", return_value={
                 "current_mode": "normal",
                 "previous_mode": "normal",
                 "recent_modes": ["normal"],
                 "summary": "当前暂无足够值班历史数据。",
                 "trend_direction": "stable",
             }):
            app.config["TESTING"] = True
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard?max_score=abc")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(captured["max_score"])

    def test_ai_dashboard_export_routes_are_registered(self):
        """Dashboard 导出中心按钮对应路由应真实可访问。"""
        from web_ui.app import app

        export_urls = [
            "/ai-dashboard/decision-brief-export?format=txt",
            "/ai-dashboard/decision-brief-export?format=csv",
            "/ai-dashboard/governance-export?export_type=governance_rules",
            "/ai-dashboard/governance-export?export_type=violations",
            "/ai-dashboard/governance-export?export_type=high_risk_targets",
            "/ai-dashboard/governance-export?export_type=today_must_do",
            "/ai-dashboard/simulation-export?export_type=scenarios",
            "/ai-dashboard/simulation-export?export_type=best_scenario",
            "/ai-dashboard/simulation-export?export_type=risk_scenario",
            "/ai-dashboard/simulation-export?export_type=simulation_history",
            "/ai-dashboard/sop-export?format=txt&sop_type=all",
            "/ai-dashboard/sop-export?format=csv&sop_type=all",
        ]

        with patch("web_ui.app.ArticleHealthService.build_ai_risk_dashboard", return_value=ArticleHealthService._empty_dashboard()):
            app.config["TESTING"] = True
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"

                for url in export_urls:
                    with self.subTest(url=url):
                        response = client.get(url)
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
                        self.assertIn("attachment; filename=", response.headers.get("Content-Disposition", ""))

    def test_ai_dashboard_export_routes_reject_invalid_params(self):
        """Dashboard 导出接口非法参数应返回明确 JSON。"""
        from web_ui.app import app

        invalid_cases = [
            ("/ai-dashboard/decision-brief-export?format=pdf", "不支持的决策简报导出格式"),
            ("/ai-dashboard/governance-export?export_type=bad", "不支持的治理导出类型"),
            ("/ai-dashboard/simulation-export?export_type=bad", "不支持的模拟导出类型"),
            ("/ai-dashboard/sop-export?format=pdf&sop_type=all", "不支持的 SOP 导出格式"),
            ("/ai-dashboard/sop-export?format=txt&sop_type=bad", "不支持的 SOP 导出类型"),
        ]

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"

            for url, expected_msg in invalid_cases:
                with self.subTest(url=url):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json(), {"ok": False, "msg": expected_msg})

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

    def test_dashboard_snapshot_missing_file_initializes_zero_changes(self):
        """快照文件不存在时应返回 0 变化，并自动写入当前快照。"""
        snapshot_path = os.path.join(self.temp_dir.name, "ai_dashboard_snapshot.json")
        dashboard = {
            "summary": {
                "high_risk_articles": 8,
                "need_attention_articles": 15,
                "avg_health_score": 74,
            }
        }
        with patch("services.article_health_service.AI_DASHBOARD_SNAPSHOT_FILE_PATH", snapshot_path):
            changes = ArticleHealthService.build_dashboard_snapshot_changes(dashboard)
            self.assertTrue(os.path.exists(snapshot_path))
            with open(snapshot_path, "r", encoding="utf-8") as snapshot_file:
                saved_snapshot = json.load(snapshot_file)

        self.assertEqual(changes["last_snapshot_time"], "")
        self.assertEqual(changes["high_risk_change"], 0)
        self.assertEqual(changes["attention_change"], 0)
        self.assertEqual(changes["avg_score_change"], 0)
        self.assertEqual(saved_snapshot["summary"]["avg_health_score"], 74)

    def test_dashboard_snapshot_corrupted_file_falls_back(self):
        """快照文件损坏时应按首次访问兜底，不让页面异常。"""
        snapshot_path = os.path.join(self.temp_dir.name, "broken_ai_dashboard_snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as snapshot_file:
            snapshot_file.write("{broken")
        with patch("services.article_health_service.AI_DASHBOARD_SNAPSHOT_FILE_PATH", snapshot_path):
            snapshot = ArticleHealthService._read_ai_dashboard_snapshot()

        self.assertEqual(snapshot, {})

    def test_dashboard_snapshot_changes_are_calculated(self):
        """快照变化应正确计算高风险、人工关注和平均分差值。"""
        snapshot_path = os.path.join(self.temp_dir.name, "compare_ai_dashboard_snapshot.json")
        previous_snapshot = {
            "created_at": "2026-05-12 10:00:00",
            "summary": {
                "high_risk_articles": 8,
                "need_attention_articles": 18,
                "avg_health_score": 69,
            },
        }
        dashboard = {
            "summary": {
                "high_risk_articles": 10,
                "need_attention_articles": 15,
                "avg_health_score": 74,
            }
        }
        with patch("services.article_health_service.AI_DASHBOARD_SNAPSHOT_FILE_PATH", snapshot_path):
            ArticleHealthService._write_ai_dashboard_snapshot(previous_snapshot)
            changes = ArticleHealthService.build_dashboard_snapshot_changes(dashboard)

        self.assertEqual(changes["last_snapshot_time"], "2026-05-12 10:00:00")
        self.assertEqual(changes["high_risk_change"], 2)
        self.assertEqual(changes["attention_change"], -3)
        self.assertEqual(changes["avg_score_change"], 5)

    def test_write_dashboard_snapshot_persists_summary(self):
        """公开写入方法应保存 Dashboard 摘要到快照文件。"""
        snapshot_path = os.path.join(self.temp_dir.name, "write_ai_dashboard_snapshot.json")
        dashboard = {
            "summary": {
                "high_risk_articles": 3,
                "need_attention_articles": 4,
                "avg_health_score": 88,
            }
        }
        with patch("services.article_health_service.AI_DASHBOARD_SNAPSHOT_FILE_PATH", snapshot_path):
            ArticleHealthService.write_ai_dashboard_snapshot(dashboard)
            with open(snapshot_path, "r", encoding="utf-8") as snapshot_file:
                snapshot = json.load(snapshot_file)

        self.assertEqual(snapshot["summary"]["high_risk_articles"], 3)
        self.assertEqual(snapshot["summary"]["need_attention_articles"], 4)
        self.assertEqual(snapshot["summary"]["avg_health_score"], 88)
        self.assertTrue(snapshot["created_at"])

    def test_dashboard_snapshot_positive_and_negative_changes(self):
        """快照变化应同时支持正向和负向差值。"""
        snapshot_path = os.path.join(self.temp_dir.name, "delta_ai_dashboard_snapshot.json")
        with patch("services.article_health_service.AI_DASHBOARD_SNAPSHOT_FILE_PATH", snapshot_path):
            ArticleHealthService._write_ai_dashboard_snapshot({
                "created_at": "2026-05-12 09:00:00",
                "summary": {
                    "high_risk_articles": 12,
                    "need_attention_articles": 6,
                    "avg_health_score": 80,
                },
            })
            changes = ArticleHealthService.build_dashboard_snapshot_changes({
                "summary": {
                    "high_risk_articles": 7,
                    "need_attention_articles": 9,
                    "avg_health_score": 72,
                }
            })

        self.assertEqual(changes["high_risk_change"], -5)
        self.assertEqual(changes["attention_change"], 3)
        self.assertEqual(changes["avg_score_change"], -8)

    def test_persistent_risk_detects_continuous_high_risk(self):
        """最近高风险日志累计达到 3 次时应识别为连续高风险。"""
        for _ in range(3):
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"})
        with self._patch_db():
            items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["high_risk_count"], 3)
        self.assertIn("连续高风险", items[0]["risk_tags"])

    def test_persistent_risk_detects_preflight_failures(self):
        """最近终检失败累计达到 2 次时应识别为连续终检失败。"""
        for _ in range(2):
            self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        with self._patch_db():
            items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual(items[0]["preflight_fail_count"], 2)
        self.assertIn("连续终检失败", items[0]["risk_tags"])

    def test_persistent_risk_detects_publish_failures(self):
        """最近发布失败任务累计达到 2 次时应识别为连续发布失败。"""
        self._insert_publish_task("failed")
        self._insert_publish_task("failed")
        with self._patch_db():
            items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual(items[0]["publish_fail_count"], 2)
        self.assertIn("连续发布失败", items[0]["risk_tags"])

    def test_persistent_risk_detects_multiple_tags(self):
        """同一篇文章命中多种连续异常时应保留全部标签。"""
        for _ in range(3):
            self._insert_log("ai_workflow", {"ok": True, "overall_risk": "high"})
        for _ in range(2):
            self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "high"})
        self._insert_publish_task("failed")
        self._insert_publish_task("failed")
        with self._patch_db():
            items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual(items[0]["risk_tags"], ["连续高风险", "连续终检失败", "连续发布失败"])
        self.assertTrue(items[0]["need_manual_attention"])

    def test_persistent_risk_sorting(self):
        """连续异常文章应按标签数量、健康分、文章 ID 排序。"""
        self._insert_article(2, "双标签文章")
        self._insert_article(3, "单标签低分文章")
        for _ in range(3):
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"}, article_id=1)
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"}, article_id=2)
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"}, article_id=3)
        for _ in range(2):
            self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False}, article_id=2)

        health_map = {
            1: {"score": 60, "risk_level": "medium", "need_manual_attention": True},
            2: {"score": 70, "risk_level": "medium", "need_manual_attention": True},
            3: {"score": 30, "risk_level": "high", "need_manual_attention": True},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]):
            with self._patch_db():
                items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual([item["article_id"] for item in items], [2, 3, 1])

    def test_persistent_risk_limit_is_capped(self):
        """limit 最大只允许返回 20 条。"""
        fake_logs = [
            {
                "action_type": "ai_review",
                "result_json": json.dumps({"risk_level": "high"}, ensure_ascii=False),
            }
            for _ in range(3)
        ]
        fake_articles = [{"id": article_id, "title": f"文章{article_id}"} for article_id in range(1, 26)]
        with patch.object(ArticleHealthService, "_list_articles_for_dashboard", return_value=fake_articles), \
             patch.object(ArticleHealthService, "_list_ai_logs", return_value=fake_logs), \
             patch.object(ArticleHealthService, "_list_publish_tasks", return_value=[]), \
             patch.object(ArticleHealthService, "build_article_health", return_value={
                 "score": 40,
                 "risk_level": "high",
                 "need_manual_attention": True,
             }):
            items = ArticleHealthService.build_persistent_risk_articles(limit=99)

        self.assertEqual(len(items), 20)

    def test_persistent_risk_empty_data(self):
        """没有连续异常信号时应返回空列表。"""
        self._insert_log("ai_review", {"ok": True, "risk_level": "medium"})
        with self._patch_db():
            items = ArticleHealthService.build_persistent_risk_articles()

        self.assertEqual(items, [])

    def test_persistent_risk_tags_generation(self):
        """risk_tags 应按固定顺序输出，便于前端稳定展示。"""
        logs = [
            {"action_type": "ai_review", "result_json": json.dumps({"risk_level": "high"}, ensure_ascii=False)},
            {"action_type": "ai_preflight", "result_json": json.dumps({"pass_preflight": False, "risk_level": "high"}, ensure_ascii=False)},
            {"action_type": "ai_workflow", "result_json": json.dumps({"overall_risk": "high"}, ensure_ascii=False)},
        ]
        publish_tasks = [{"status": "failed"}, {"status": "failed"}]
        self.assertEqual(ArticleHealthService._count_recent_high_risk_logs(logs), 3)
        self.assertEqual(ArticleHealthService._count_recent_preflight_failures(logs), 1)
        self.assertEqual(sum(1 for task in publish_tasks if task.get("status") == "failed"), 2)

    def test_recovered_articles_detect_high_risk_recovery(self):
        """过去连续高风险、当前已非 high 时应识别为恢复。"""
        for _ in range(3):
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"})
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 82,
            "risk_level": "low",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 12,
            "trend_direction": "up",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertIn("高风险已恢复", items[0]["recovered_tags"])

    def test_recovered_articles_detect_preflight_recovery(self):
        """过去连续终检失败、最近终检通过时应识别为恢复。"""
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": True, "risk_level": "low"})
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 78,
            "risk_level": "medium",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 8,
            "trend_direction": "up",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertIn("终检已恢复", items[0]["recovered_tags"])

    def test_recovered_articles_detect_publish_failure_recovery(self):
        """过去连续发布失败、最近成功时应识别为恢复。"""
        self._insert_publish_task("failed")
        self._insert_publish_task("failed")
        self._insert_publish_task("success")
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 85,
            "risk_level": "low",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 10,
            "trend_direction": "up",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertIn("发布失败已恢复", items[0]["recovered_tags"])

    def test_recovered_articles_detect_score_change(self):
        """score_change >= 20 时即使无恢复标签也应入榜。"""
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 88,
            "risk_level": "low",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 24,
            "trend_direction": "up",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["score_change"], 24)
        self.assertEqual(items[0]["recovered_tags"], [])

    def test_recovered_articles_tags_are_correct(self):
        """恢复标签应按规则聚合输出。"""
        for _ in range(3):
            self._insert_log("ai_review", {"ok": True, "risk_level": "high"})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": False, "risk_level": "medium"})
        self._insert_log("ai_preflight", {"ok": True, "pass_preflight": True, "risk_level": "low"})
        self._insert_publish_task("failed")
        self._insert_publish_task("failed")
        self._insert_publish_task("success")
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 90,
            "risk_level": "low",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 30,
            "trend_direction": "up",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertEqual(items[0]["recovered_tags"], ["高风险已恢复", "终检已恢复", "发布失败已恢复"])

    def test_recovered_articles_sorting(self):
        """恢复文章应按分数变化、标签数量、文章 ID 排序。"""
        self._insert_article(2, "恢复文章2")
        self._insert_article(3, "恢复文章3")
        health_map = {
            1: {"score": 80, "risk_level": "low"},
            2: {"score": 85, "risk_level": "low"},
            3: {"score": 90, "risk_level": "low"},
        }
        trend_map = {
            1: {"score_change": 25, "trend_direction": "up"},
            2: {"score_change": 35, "trend_direction": "up"},
            3: {"score_change": 35, "trend_direction": "up"},
        }
        with patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map[article_id]), \
             patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map[article_id]):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertEqual([item["article_id"] for item in items], [2, 3, 1])

    def test_recovered_articles_limit_is_capped(self):
        """恢复文章 limit 最大返回 20 条。"""
        fake_articles = [{"id": article_id, "title": f"文章{article_id}"} for article_id in range(1, 26)]
        with patch.object(ArticleHealthService, "_list_articles_for_dashboard", return_value=fake_articles), \
             patch.object(ArticleHealthService, "_list_ai_logs", return_value=[]), \
             patch.object(ArticleHealthService, "_list_publish_tasks", return_value=[]), \
             patch.object(ArticleHealthService, "build_article_health", return_value={"score": 88, "risk_level": "low"}), \
             patch.object(ArticleHealthService, "build_health_trend", return_value={"score_change": 22, "trend_direction": "up"}):
            items = ArticleHealthService.build_recovered_articles(limit=99)

        self.assertEqual(len(items), 20)

    def test_recovered_articles_empty_data(self):
        """没有恢复信号且分数变化不足时应返回空列表。"""
        with patch.object(ArticleHealthService, "build_article_health", return_value={
            "score": 70,
            "risk_level": "medium",
        }), patch.object(ArticleHealthService, "build_health_trend", return_value={
            "score_change": 5,
            "trend_direction": "stable",
        }):
            with self._patch_db():
                items = ArticleHealthService.build_recovered_articles()

        self.assertEqual(items, [])

    def test_ai_ops_suggestions_high_risk_rule(self):
        """高风险文章达到阈值时应生成 danger 建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"high_risk_articles": 5, "avg_health_score": 80},
        })
        self.assertEqual(suggestions[0]["title"], "存在多篇高风险文章")
        self.assertEqual(suggestions[0]["level"], "danger")

    def test_ai_ops_suggestions_persistent_rule(self):
        """连续异常文章较多时应生成 warning 建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"avg_health_score": 80},
            "persistent_risk_articles": [{}, {}, {}],
        })
        self.assertEqual(suggestions[0]["title"], "连续异常文章较多")
        self.assertEqual(suggestions[0]["level"], "warning")

    def test_ai_ops_suggestions_recovery_rule(self):
        """恢复文章数量不少于连续异常时应生成 success 建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"avg_health_score": 80},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [{}, {}],
        })
        self.assertEqual(suggestions[0]["title"], "近期风险恢复情况良好")
        self.assertEqual(suggestions[0]["level"], "success")

    def test_ai_ops_suggestions_avg_score_rule(self):
        """平均健康分偏低时应生成 danger 建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"avg_health_score": 59},
        })
        self.assertEqual(suggestions[0]["title"], "整体文章健康分偏低")
        self.assertEqual(suggestions[0]["action_url"], "/ai-dashboard?max_score=60")

    def test_ai_ops_suggestions_active_rule(self):
        """AI 操作次数过高时应生成 warning 建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"avg_health_score": 80},
            "top_active_articles": [{"ai_operation_count": 10}],
        })
        self.assertEqual(suggestions[0]["title"], "部分文章 AI 操作过于频繁")
        self.assertEqual(suggestions[0]["level"], "warning")

    def test_ai_ops_suggestions_level_sorting(self):
        """建议应按 danger、warning、success 顺序排序。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"high_risk_articles": 5, "avg_health_score": 40},
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [{}, {}, {}],
            "top_active_articles": [{"ai_operation_count": 12}],
        })
        self.assertEqual([item["level"] for item in suggestions], ["danger", "danger", "warning", "warning", "success"])

    def test_ai_ops_suggestions_limit_five(self):
        """建议数量最多返回 5 条。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"high_risk_articles": 8, "avg_health_score": 40},
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [{}, {}, {}],
            "top_active_articles": [{"ai_operation_count": 15}],
        })
        self.assertEqual(len(suggestions), 5)

    def test_ai_ops_suggestions_empty(self):
        """没有命中规则时应返回空建议。"""
        suggestions = ArticleHealthService.build_ai_ops_suggestions({
            "summary": {"high_risk_articles": 1, "avg_health_score": 88},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "top_active_articles": [{"ai_operation_count": 2}],
        })
        self.assertEqual(suggestions, [])

    def test_daily_ai_ops_summary_danger_level(self):
        """高风险摘要应优先判定为 danger。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 5,
                "avg_health_score": 58,
                "need_attention_articles": 2,
            },
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 1},
        })
        self.assertEqual(result["level"], "danger")
        self.assertEqual(result["title"], "今日 AI 风险偏高")

    def test_daily_ai_ops_summary_warning_level(self):
        """需要关注但未触发 danger 时应判定为 warning。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 1,
                "avg_health_score": 72,
                "need_attention_articles": 5,
            },
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [{}, {}, {}],
            "trend_summary": {"down_count": 2},
        })
        self.assertEqual(result["level"], "warning")
        self.assertEqual(result["title"], "今日 AI 运营需要关注")

    def test_daily_ai_ops_summary_good_level(self):
        """恢复面良好时应判定为 good。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 0,
                "avg_health_score": 82,
                "need_attention_articles": 1,
            },
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [{}, {}],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 0},
        })
        self.assertEqual(result["level"], "good")
        self.assertEqual(result["title"], "今日 AI 运营表现良好")

    def test_daily_ai_ops_summary_normal_level(self):
        """未命中其他等级时应保持 normal。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 2,
                "avg_health_score": 78,
                "need_attention_articles": 3,
            },
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 1},
        })
        self.assertEqual(result["level"], "normal")
        self.assertEqual(result["title"], "今日 AI 运营整体稳定")

    def test_daily_ai_ops_summary_contains_key_metrics(self):
        """summary 和 highlights 应带出关键运营指标。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 2,
                "avg_health_score": 78,
                "need_attention_articles": 5,
            },
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}, {}, {}],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 4},
        })
        self.assertIn("平均健康分 78", result["summary"])
        self.assertIn("高风险文章 2 篇", result["summary"])
        self.assertIn("需人工关注 5 篇", result["summary"])
        self.assertIn("连续异常文章 1 篇", result["summary"])
        self.assertIn("恢复文章 3 篇", result["summary"])
        self.assertIn("趋势下降文章：4", result["highlights"])

    def test_daily_ai_ops_summary_recommended_focus(self):
        """recommended_focus 应按命中信号补齐建议。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 1,
                "avg_health_score": 76,
                "need_attention_articles": 2,
            },
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}],
            "recent_fail_articles": [{}],
            "trend_summary": {"down_count": 1},
        })
        self.assertEqual(result["recommended_focus"], [
            "优先处理高风险文章",
            "优先处理连续异常文章",
            "检查最近发布失败文章",
            "关注健康趋势下降文章",
            "复盘已恢复文章的优化路径",
        ])

    def test_daily_ai_ops_summary_empty_dashboard(self):
        """空 dashboard 应返回稳定兜底摘要。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({})
        self.assertEqual(result["level"], "normal")
        self.assertEqual(result["title"], "今日 AI 运营暂无异常")
        self.assertEqual(result["highlights"], [])
        self.assertEqual(result["recommended_focus"], ["保持当前审核与终检节奏"])

    def test_daily_ai_ops_summary_level_priority(self):
        """等级优先级应保持 danger > warning > good > normal。"""
        result = ArticleHealthService.build_daily_ai_ops_summary({
            "summary": {
                "high_risk_articles": 5,
                "avg_health_score": 88,
                "need_attention_articles": 8,
            },
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [{}, {}, {}, {}],
            "recent_fail_articles": [{}, {}, {}],
            "trend_summary": {"down_count": 4},
        })
        self.assertEqual(result["level"], "danger")

    def test_ai_ops_report_text_normal_dashboard(self):
        """正常 Dashboard 应生成完整日报文本。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营需要关注",
                "highlights": [
                    "平均健康分：72",
                    "高风险文章：3",
                    "需人工关注：6",
                ],
                "recommended_focus": [
                    "优先处理高风险文章",
                    "检查最近发布失败文章",
                ],
            },
            "ai_ops_suggestions": [
                {
                    "level": "danger",
                    "title": "存在多篇高风险文章",
                    "message": "建议优先处理健康分最低的文章",
                }
            ],
        })
        self.assertIn("【AI 公众号运营日报】", report)
        self.assertIn("今日 AI 运营状态：今日 AI 运营需要关注", report)
        self.assertIn("- 平均健康分：72", report)
        self.assertIn("- 存在多篇高风险文章，建议优先处理健康分最低的文章", report)
        self.assertIn("1. 优先处理高风险文章", report)

    def test_ai_ops_report_text_filters_success_suggestions(self):
        """日报重点风险只应保留 danger/warning 建议。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：78"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_suggestions": [
                {"level": "success", "title": "近期恢复良好", "message": "继续保持"},
                {"level": "warning", "title": "连续异常文章较多", "message": "建议先处理"},
            ],
        })
        self.assertIn("连续异常文章较多", report)
        self.assertNotIn("近期恢复良好", report)

    def test_ai_ops_report_text_limits_risk_items_to_five(self):
        """日报中的重点风险最多保留 5 条。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 风险偏高",
                "highlights": ["平均健康分：55"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_suggestions": [
                {
                    "level": "warning",
                    "title": f"风险{i}",
                    "message": "需要处理",
                }
                for i in range(6)
            ],
        })
        self.assertIn("风险0", report)
        self.assertIn("风险4", report)
        self.assertNotIn("风险5", report)

    def test_ai_ops_report_text_empty_dashboard(self):
        """空 Dashboard 应生成稳定兜底日报。"""
        report = ArticleHealthService.build_ai_ops_report_text({})
        self.assertIn("今日 AI 运营状态：暂无足够数据", report)
        self.assertIn("- 暂无数据", report)
        self.assertIn("1. 保持当前审核与终检节奏", report)

    def test_ai_ops_report_text_includes_score(self):
        """日报应包含 AI 运营总评分与等级。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_score": {
                "score": 82,
                "level": "good",
                "summary": "当前 AI 运营整体稳定，风险可控。",
            },
        })
        self.assertIn("AI 运营总评分：", report)
        self.assertIn("- 当前评分：82", report)
        self.assertIn("- 等级：良好", report)
        self.assertIn("- 说明：当前 AI 运营整体稳定，风险可控。", report)

    def test_ai_ops_report_text_includes_score_trend(self):
        """日报应包含 AI 运营评分趋势。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_score_trend": {
                "previous_score": 75,
                "current_score": 82,
                "score_change": 7,
                "trend_direction": "up",
                "recent_scores": [60, 65, 70, 75, 82],
            },
        })
        self.assertIn("AI 运营评分趋势：", report)
        self.assertIn("- 上次评分：75", report)
        self.assertIn("- 当前评分：82", report)
        self.assertIn("- 变化：+7", report)
        self.assertIn("- 趋势：上升", report)
        self.assertIn("- 轨迹：60 → 65 → 70 → 75 → 82", report)

    def test_ai_ops_report_text_score_change_negative_and_zero(self):
        """日报评分变化应正确展示负数和 0。"""
        negative_report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 风险偏高",
                "highlights": [],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_score_trend": {
                "previous_score": 82,
                "current_score": 75,
                "score_change": -7,
                "trend_direction": "down",
                "recent_scores": [],
            },
        })
        stable_report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": [],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_score_trend": {
                "previous_score": 82,
                "current_score": 82,
                "score_change": 0,
                "trend_direction": "stable",
                "recent_scores": [],
            },
        })
        self.assertIn("- 变化：-7", negative_report)
        self.assertIn("- 变化：0", stable_report)
        self.assertIn("- 轨迹：-", stable_report)

    def test_ai_ops_report_text_missing_score_fallback(self):
        """缺失 ai_ops_score 时应显示评分兜底。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
        })
        self.assertIn("AI 运营总评分：", report)
        self.assertIn("- 暂无评分数据", report)

    def test_ai_ops_report_text_missing_trend_fallback(self):
        """缺失 ai_ops_score_trend 时应显示趋势兜底。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_score": {
                "score": 82,
                "level": "good",
                "summary": "当前 AI 运营整体稳定，风险可控。",
            },
        })
        self.assertIn("AI 运营评分趋势：", report)
        self.assertIn("- 暂无趋势数据", report)

    def test_ai_ops_report_text_includes_incident_feed(self):
        """日报应包含重要播报板块。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_incident_feed": [
                {
                    "level": "danger",
                    "title": "文章进入连续异常状态",
                    "message": "《文章A》存在：连续高风险、连续终检失败",
                },
                {
                    "level": "success",
                    "title": "文章风险已恢复",
                    "message": "《文章B》健康分从 45 提升至 82",
                },
            ],
        })
        self.assertIn("重要播报：", report)
        self.assertIn("1. [高风险] 文章进入连续异常状态： 《文章A》存在：连续高风险、连续终检失败", report)
        self.assertIn("2. [良好] 文章风险已恢复： 《文章B》健康分从 45 提升至 82", report)

    def test_ai_ops_report_text_limits_incident_feed_to_five(self):
        """日报重要播报最多保留 5 条。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_incident_feed": [
                {"level": "warning", "title": f"事件{i}", "message": "需要关注"}
                for i in range(6)
            ],
        })
        self.assertIn("事件0", report)
        self.assertIn("事件4", report)
        self.assertNotIn("事件5", report)

    def test_ai_ops_report_text_empty_incident_feed(self):
        """无播报时日报应显示空状态。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_incident_feed": [],
        })
        self.assertIn("重要播报：", report)
        self.assertIn("- 当前暂无重要播报", report)

    def test_ai_ops_report_text_incident_feed_field_fallback(self):
        """播报字段缺失时日报应使用兜底文案。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_incident_feed": [{}],
        })
        self.assertIn("1. [信息] 未命名事件：", report)

    def test_ai_ops_report_text_includes_priority_queue(self):
        """日报应包含优先处理队列板块。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [
                {
                    "title": "文章A",
                    "priority_level": "critical",
                    "priority_score": 92,
                    "reasons": ["连续高风险", "连续终检失败", "健康分过低"],
                }
            ],
        })

        self.assertIn("优先处理队列：", report)
        self.assertIn("1. 《文章A》｜优先级 紧急｜分数 92｜原因：连续高风险、连续终检失败、健康分过低", report)

    def test_ai_ops_report_text_limits_priority_queue_to_five(self):
        """日报优先处理队列最多展示 5 条。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [
                {
                    "title": f"文章{i}",
                    "priority_level": "high",
                    "priority_score": 80 - i,
                    "reasons": ["存在发布失败"],
                }
                for i in range(6)
            ],
        })

        self.assertIn("文章0", report)
        self.assertIn("文章4", report)
        self.assertNotIn("文章5", report)

    def test_ai_ops_report_text_priority_reasons_joined(self):
        """优先处理原因应使用顿号拼接。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [
                {
                    "title": "文章B",
                    "priority_level": "high",
                    "priority_score": 75,
                    "reasons": ["存在发布失败", "需人工关注"],
                }
            ],
        })

        self.assertIn("原因：存在发布失败、需人工关注", report)

    def test_ai_ops_report_text_priority_empty_reasons(self):
        """优先处理队列原因为空时应显示兜底原因。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [
                {
                    "title": "文章C",
                    "priority_level": "medium",
                    "priority_score": 45,
                    "reasons": [],
                }
            ],
        })

        self.assertIn("原因：暂无明确原因", report)

    def test_ai_ops_report_text_empty_priority_queue(self):
        """无优先处理文章时日报应显示空状态。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [],
        })

        self.assertIn("优先处理队列：", report)
        self.assertIn("- 当前暂无优先处理文章", report)

    def test_ai_ops_report_text_priority_field_fallback(self):
        """优先处理队列字段缺失时应使用兜底文案。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_priority_queue": [{}],
        })

        self.assertIn("1. 《未知文章》｜优先级 未知｜分数 0｜原因：暂无明确原因", report)

    def test_ai_ops_duty_mode_high_alert(self):
        """连续异常较多时应进入高危值班模式。"""
        result = ArticleHealthService.build_ai_ops_duty_mode({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["mode"], "high_alert")
        self.assertEqual(result["badge"], "danger")
        self.assertIn("高危值班模式", result["title"])
        self.assertIn("立即重点处理", result["recommended_action"])

    def test_ai_ops_duty_mode_focus(self):
        """存在高风险文章时应进入重点关注模式。"""
        result = ArticleHealthService.build_ai_ops_duty_mode({
            "summary": {"high_risk_articles": 1, "need_attention_articles": 1},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["mode"], "focus")
        self.assertEqual(result["badge"], "warning")
        self.assertEqual(result["description"], "当前仍存在部分高风险与人工关注文章，需要重点巡检。")

    def test_ai_ops_duty_mode_recovery(self):
        """恢复文章多于连续异常时应进入恢复观察模式。"""
        result = ArticleHealthService.build_ai_ops_duty_mode({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}, {}],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["mode"], "recovery")
        self.assertEqual(result["badge"], "success")
        self.assertIn("复盘恢复文章", result["recommended_action"])

    def test_ai_ops_duty_mode_normal(self):
        """无明显异常时应进入稳定巡检模式。"""
        result = ArticleHealthService.build_ai_ops_duty_mode({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["mode"], "normal")
        self.assertEqual(result["badge"], "secondary")
        self.assertEqual(result["recommended_action"], "保持当前审核与终检节奏即可。")

    def test_ai_ops_report_text_includes_duty_mode(self):
        """日报应包含当前值班模式。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_duty_mode": {
                "title": "AI 运营高危值班模式",
                "recommended_action": "建议立即重点处理高风险与连续终检失败文章。",
            },
        })

        self.assertIn("当前值班模式：", report)
        self.assertIn("- AI 运营高危值班模式", report)
        self.assertIn("- 建议立即重点处理高风险与连续终检失败文章。", report)

    def test_ai_ops_duty_mode_empty_dashboard(self):
        """空 Dashboard 应返回默认巡检模式。"""
        result = ArticleHealthService.build_ai_ops_duty_mode({})

        self.assertEqual(result["mode"], "normal")
        self.assertEqual(result["title"], "AI 运营默认巡检模式")
        self.assertEqual(result["badge"], "secondary")

    def test_ai_ops_conclusion_danger(self):
        """连续异常较多时应生成 danger 运营结论。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["risk_level"], "danger")
        self.assertEqual(result["top_issue"], "连续异常文章较多")
        self.assertEqual(result["top_action"], "优先处理高风险与连续终检失败文章")

    def test_ai_ops_conclusion_warning(self):
        """存在高风险文章时应生成 warning 运营结论。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 1, "need_attention_articles": 1},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["risk_level"], "warning")
        self.assertEqual(result["title"], "当前 AI 运营存在一定风险")
        self.assertEqual(result["top_issue"], "高风险文章较多")

    def test_ai_ops_conclusion_good(self):
        """恢复文章多于连续异常时应生成 good 运营结论。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}, {}],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["risk_level"], "good")
        self.assertEqual(result["title"], "当前 AI 运营恢复情况良好")

    def test_ai_ops_conclusion_normal(self):
        """无明显异常时应生成 normal 运营结论。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["risk_level"], "normal")
        self.assertEqual(result["top_issue"], "暂无明显问题")
        self.assertEqual(result["top_action"], "保持当前审核与终检节奏")

    def test_ai_ops_conclusion_top_issue_score_down(self):
        """评分下降但未达 danger 时核心问题应指向评分下降。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -5},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
        })

        self.assertEqual(result["top_issue"], "AI 运营评分下降")
        self.assertEqual(result["top_action"], "关注健康趋势下降文章")

    def test_ai_ops_conclusion_top_action_publish_fail(self):
        """没有高风险但存在发布失败时应建议检查发布失败文章。"""
        result = ArticleHealthService.build_ai_ops_conclusion({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "ai_ops_score": {"level": "good"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [{}, {}, {}],
        })

        self.assertEqual(result["top_issue"], "最近发布失败较多")
        self.assertEqual(result["top_action"], "检查最近发布失败文章")

    def test_ai_ops_report_text_includes_conclusion(self):
        """日报末尾应包含运营结论。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["优先处理高风险文章"],
            },
            "ai_ops_conclusion": {
                "risk_level": "warning",
                "title": "当前 AI 运营存在一定风险",
                "top_issue": "连续异常文章较多",
                "top_action": "优先处理高风险与连续终检失败文章",
            },
        })

        self.assertIn("运营结论：", report)
        self.assertIn("- 风险等级：警告", report)
        self.assertIn("- 结论：当前 AI 运营存在一定风险", report)
        self.assertIn("- 核心问题：连续异常文章较多", report)
        self.assertIn("- 当前建议动作：优先处理高风险与连续终检失败文章", report)

    def test_ai_ops_report_text_conclusion_fallback(self):
        """日报缺失 conclusion 时应动态生成兜底结论。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {
                "title": "今日 AI 运营整体稳定",
                "highlights": ["平均健康分：82"],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
        })

        self.assertIn("运营结论：", report)
        self.assertIn("- 风险等级：正常", report)
        self.assertIn("- 核心问题：暂无明显问题", report)

    def test_ai_ops_incident_feed_persistent_risk(self):
        """连续异常文章应生成 danger 播报。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "persistent_risk_articles": [{
                "title": "文章A",
                "risk_tags": ["连续高风险", "连续终检失败"],
            }],
        })
        self.assertEqual(incidents[0]["level"], "danger")
        self.assertEqual(incidents[0]["title"], "文章进入连续异常状态")
        self.assertIn("《文章A》存在：连续高风险、连续终检失败", incidents[0]["message"])
        self.assertIn("created_at", incidents[0])

    def test_ai_ops_incident_feed_recovered_article(self):
        """风险恢复文章应生成 success 播报。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "recovered_articles": [{
                "title": "文章B",
                "previous_score": 45,
                "current_score": 82,
            }],
        })
        self.assertEqual(incidents[0]["level"], "success")
        self.assertEqual(incidents[0]["title"], "文章风险已恢复")
        self.assertIn("健康分从 45 提升至 82", incidents[0]["message"])

    def test_ai_ops_incident_feed_score_down(self):
        """评分明显下降应生成 danger 播报。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "ai_ops_score_trend": {"score_change": -12},
        })
        self.assertEqual(incidents[0]["title"], "AI 运营评分明显下降")
        self.assertIn("当前评分下降 -12", incidents[0]["message"])

    def test_ai_ops_incident_feed_score_up(self):
        """评分明显提升应生成 success 播报。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "ai_ops_score_trend": {"score_change": 12},
        })
        self.assertEqual(incidents[0]["level"], "success")
        self.assertEqual(incidents[0]["title"], "AI 运营评分明显提升")
        self.assertIn("当前评分提升 +12", incidents[0]["message"])

    def test_ai_ops_incident_feed_suggestion_event(self):
        """danger/warning 运营建议应进入播报。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "ai_ops_suggestions": [
                {"level": "success", "title": "恢复良好", "message": "继续保持"},
                {"level": "warning", "title": "连续异常文章较多", "message": "建议先处理"},
            ],
        })
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["level"], "warning")
        self.assertEqual(incidents[0]["title"], "连续异常文章较多")

    def test_ai_ops_incident_feed_level_sorting(self):
        """播报应按 danger、warning、success 排序。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "recovered_articles": [{"title": "文章C", "previous_score": 40, "current_score": 80}],
            "ai_ops_suggestions": [{"level": "warning", "title": "警告", "message": "关注"}],
            "ai_ops_score_trend": {"score_change": -10},
        })
        self.assertEqual([item["level"] for item in incidents], ["danger", "warning", "success"])

    def test_ai_ops_incident_feed_limit_ten(self):
        """播报最多返回 10 条。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({
            "persistent_risk_articles": [
                {"title": f"文章{i}", "risk_tags": ["连续高风险"]}
                for i in range(12)
            ],
        })
        self.assertEqual(len(incidents), 10)

    def test_ai_ops_incident_feed_empty(self):
        """无事件来源时应返回空列表。"""
        incidents = ArticleHealthService.build_ai_ops_incident_feed({})
        self.assertEqual(incidents, [])

    def test_ai_ops_priority_queue_score_calculation(self):
        """优先处理队列应按风险来源累计 priority_score。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "top_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "score": 35,
                "risk_level": "high",
                "trend_direction": "down",
                "need_manual_attention": True,
            }],
            "persistent_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "health_score": 35,
                "risk_level": "high",
                "risk_tags": ["连续高风险", "连续终检失败"],
                "need_manual_attention": True,
            }],
            "recent_fail_articles": [{
                "article_id": 1,
                "title": "文章A",
                "failed_count": 2,
            }],
            "recovered_articles": [],
        })

        self.assertEqual(queue[0]["priority_score"], 135)
        self.assertEqual(queue[0]["priority_level"], "critical")

    def test_ai_ops_priority_queue_level_high(self):
        """priority_score 60~79 应判定为 high。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "top_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "score": 55,
                "risk_level": "high",
                "need_manual_attention": True,
            }],
            "persistent_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "health_score": 55,
                "risk_tags": ["连续高风险"],
            }],
        })

        self.assertEqual(queue[0]["priority_score"], 70)
        self.assertEqual(queue[0]["priority_level"], "high")

    def test_ai_ops_priority_queue_level_medium(self):
        """priority_score 40~59 应判定为 medium。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "top_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "score": 50,
                "risk_level": "high",
            }],
        })

        self.assertEqual(queue[0]["priority_score"], 40)
        self.assertEqual(queue[0]["priority_level"], "medium")

    def test_ai_ops_priority_queue_level_low(self):
        """priority_score 小于 40 应判定为 low。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "recent_fail_articles": [{
                "article_id": 1,
                "title": "文章A",
            }],
        })

        self.assertEqual(queue[0]["priority_score"], 15)
        self.assertEqual(queue[0]["priority_level"], "low")

    def test_ai_ops_priority_queue_reasons(self):
        """优先处理原因应覆盖高风险、人工关注、趋势下降和发布失败。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "top_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "score": 45,
                "risk_level": "high",
                "trend_direction": "down",
                "need_manual_attention": True,
            }],
            "recent_fail_articles": [{"article_id": 1, "title": "文章A"}],
        })

        self.assertIn("高风险文章", queue[0]["reasons"])
        self.assertIn("需人工关注", queue[0]["reasons"])
        self.assertIn("健康分过低", queue[0]["reasons"])
        self.assertIn("趋势下降", queue[0]["reasons"])
        self.assertIn("存在发布失败", queue[0]["reasons"])

    def test_ai_ops_priority_queue_sorting(self):
        """优先队列应按 priority_score 降序、health_score 升序、article_id 升序排序。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "top_risk_articles": [
                {"article_id": 3, "title": "文章C", "score": 30, "risk_level": "high"},
                {"article_id": 1, "title": "文章A", "score": 20, "risk_level": "high"},
                {"article_id": 2, "title": "文章B", "score": 20, "risk_level": "high"},
            ],
        })

        self.assertEqual([item["article_id"] for item in queue], [1, 2, 3])

    def test_ai_ops_priority_queue_limit(self):
        """优先队列 limit 最大保护为 20。"""
        queue = ArticleHealthService.build_ai_ops_priority_queue({
            "recent_fail_articles": [
                {"article_id": article_id, "title": f"文章{article_id}"}
                for article_id in range(1, 31)
            ],
        }, limit=99)

        self.assertEqual(len(queue), 20)

    def test_ai_ops_priority_queue_empty(self):
        """无风险来源时应返回空队列。"""
        self.assertEqual(ArticleHealthService.build_ai_ops_priority_queue({}), [])

    def test_ai_ops_score_deductions_and_breakdown(self):
        """AI 运营总评分应按风险项扣分并保留拆解。"""
        result = ArticleHealthService.build_ai_ops_score({
            "summary": {
                "high_risk_articles": 3,
                "need_attention_articles": 4,
                "avg_health_score": 72,
            },
            "persistent_risk_articles": [{}, {}],
            "recent_fail_articles": [{}, {}],
            "recovered_articles": [],
            "trend_summary": {"down_count": 3},
        })
        self.assertEqual(result["score"], 57)
        self.assertEqual(result["level"], "danger")
        breakdown = {item["name"]: item["score"] for item in result["score_breakdown"]}
        self.assertEqual(breakdown["高风险文章"], -15)
        self.assertEqual(breakdown["连续异常文章"], -8)
        self.assertEqual(breakdown["人工关注文章"], -8)
        self.assertEqual(breakdown["最近失败文章"], -6)
        self.assertEqual(breakdown["趋势下降文章"], -6)

    def test_ai_ops_score_bonuses(self):
        """恢复文章、健康分高和无高风险时应加分。"""
        result = ArticleHealthService.build_ai_ops_score({
            "summary": {
                "high_risk_articles": 0,
                "need_attention_articles": 0,
                "avg_health_score": 90,
            },
            "persistent_risk_articles": [],
            "recent_fail_articles": [],
            "recovered_articles": [{}, {}, {}],
            "trend_summary": {"down_count": 0},
        })
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["level"], "excellent")
        breakdown = {item["name"]: item["score"] for item in result["score_breakdown"]}
        self.assertEqual(breakdown["平均健康分"], 5)
        self.assertEqual(breakdown["恢复文章"], 6)
        self.assertEqual(breakdown["无高风险文章"], 5)

    def test_ai_ops_score_score_clamped_to_zero(self):
        """严重异常场景下评分最低不应低于 0。"""
        result = ArticleHealthService.build_ai_ops_score({
            "summary": {
                "high_risk_articles": 99,
                "need_attention_articles": 99,
                "avg_health_score": 20,
            },
            "persistent_risk_articles": [{} for _ in range(99)],
            "recent_fail_articles": [{} for _ in range(99)],
            "recovered_articles": [],
            "trend_summary": {"down_count": 99},
        })
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["level"], "danger")

    def test_ai_ops_score_warning_level(self):
        """60~74 分应判定为 warning。"""
        result = ArticleHealthService.build_ai_ops_score({
            "summary": {
                "high_risk_articles": 2,
                "need_attention_articles": 3,
                "avg_health_score": 70,
            },
            "persistent_risk_articles": [{}],
            "recent_fail_articles": [{}],
            "recovered_articles": [],
            "trend_summary": {"down_count": 2},
        })
        self.assertEqual(result["score"], 73)
        self.assertEqual(result["level"], "warning")

    def test_ai_ops_score_danger_level(self):
        """低分场景应判定为 danger。"""
        result = ArticleHealthService.build_ai_ops_score({
            "summary": {
                "high_risk_articles": 6,
                "need_attention_articles": 6,
                "avg_health_score": 50,
            },
            "persistent_risk_articles": [{}, {}, {}],
            "recent_fail_articles": [{}, {}, {}],
            "recovered_articles": [],
            "trend_summary": {"down_count": 4},
        })
        self.assertLess(result["score"], 60)
        self.assertEqual(result["level"], "danger")

    def test_ai_ops_score_empty_dashboard(self):
        """空 Dashboard 应返回稳定兜底评分。"""
        result = ArticleHealthService.build_ai_ops_score({})
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["level"], "good")
        self.assertEqual(result["score_breakdown"], [])
        self.assertIn("默认按稳定状态处理", result["summary"])

    def test_ai_ops_score_history_write(self):
        """评分历史应能正常写入本地 JSON 文件。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService.append_ai_ops_score_history(78)
            history = ArticleHealthService._read_ai_ops_score_history()

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["score"], 78)
        self.assertIn("created_at", history[0])

    def test_ai_ops_score_history_skips_duplicate_score(self):
        """最近一次评分相同时不应重复写入历史。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_duplicate.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService.append_ai_ops_score_history(82)
            ArticleHealthService.append_ai_ops_score_history(82)
            history = ArticleHealthService._read_ai_ops_score_history()

        self.assertEqual(len(history), 1)

    def test_ai_ops_score_trend_up(self):
        """评分变化 >= 5 时应判定为 up。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_up.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_score_history([
                {"created_at": "2026-05-12 10:00:00", "score": 75}
            ])
            trend = ArticleHealthService.build_ai_ops_score_trend({
                "ai_ops_score": {"score": 82}
            })

        self.assertEqual(trend["previous_score"], 75)
        self.assertEqual(trend["score_change"], 7)
        self.assertEqual(trend["trend_direction"], "up")

    def test_ai_ops_score_trend_down(self):
        """评分变化 <= -5 时应判定为 down。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_down.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_score_history([
                {"created_at": "2026-05-12 10:00:00", "score": 82}
            ])
            trend = ArticleHealthService.build_ai_ops_score_trend({
                "ai_ops_score": {"score": 74}
            })

        self.assertEqual(trend["score_change"], -8)
        self.assertEqual(trend["trend_direction"], "down")
        self.assertIn("下降趋势", trend["summary"])

    def test_ai_ops_score_trend_stable(self):
        """评分变化不足 5 分时应判定为 stable。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_stable.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_score_history([
                {"created_at": "2026-05-12 10:00:00", "score": 80}
            ])
            trend = ArticleHealthService.build_ai_ops_score_trend({
                "ai_ops_score": {"score": 83}
            })

        self.assertEqual(trend["score_change"], 3)
        self.assertEqual(trend["trend_direction"], "stable")

    def test_ai_ops_score_trend_recent_scores(self):
        """趋势应返回最近评分轨迹。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_recent.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_score_history([
                {"created_at": "2026-05-12 07:00:00", "score": 60},
                {"created_at": "2026-05-12 08:00:00", "score": 65},
                {"created_at": "2026-05-12 09:00:00", "score": 70},
                {"created_at": "2026-05-12 10:00:00", "score": 75},
            ])
            trend = ArticleHealthService.build_ai_ops_score_trend({
                "ai_ops_score": {"score": 82}
            })

        self.assertEqual(trend["recent_scores"], [60, 65, 70, 75, 82])

    def test_ai_ops_score_history_broken_file(self):
        """评分历史文件损坏时应兜底为空列表。"""
        history_path = os.path.join(self.temp_dir.name, "broken_ai_ops_score_history.json")
        with open(history_path, "w", encoding="utf-8") as history_file:
            history_file.write("{broken")

        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            history = ArticleHealthService._read_ai_ops_score_history()

        self.assertEqual(history, [])

    def test_ai_ops_score_history_keeps_latest_100(self):
        """评分历史最多保留最近 100 条。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_score_history_limit.json")
        with patch("services.article_health_service.AI_OPS_SCORE_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_score_history([
                {"created_at": f"2026-05-12 10:{index:02d}:00", "score": index}
                for index in range(101)
            ])
            history = ArticleHealthService._read_ai_ops_score_history()

        self.assertEqual(len(history), 100)
        self.assertEqual(history[0]["score"], 1)
        self.assertEqual(history[-1]["score"], 100)


    def test_ai_ops_duty_history_write(self):
        """值班历史应能正常写入本地 JSON 文件。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService.append_ai_ops_duty_history({
                "mode": "normal",
                "title": "AI 运营稳定巡检模式",
            })
            history = ArticleHealthService._read_ai_ops_duty_history()

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["mode"], "normal")
        self.assertIn("created_at", history[0])

    def test_ai_ops_duty_history_skips_duplicate_mode(self):
        """最近一次值班模式相同时不应重复写入历史。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_duplicate.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService.append_ai_ops_duty_history({"mode": "focus", "title": "AI 运营重点关注模式"})
            ArticleHealthService.append_ai_ops_duty_history({"mode": "focus", "title": "AI 运营重点关注模式"})
            history = ArticleHealthService._read_ai_ops_duty_history()

        self.assertEqual(len(history), 1)

    def test_ai_ops_duty_history_trend_up(self):
        """值班模式严重程度升级时应判定为 up。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_up.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_duty_history([
                {"created_at": "2026-05-12 10:00:00", "mode": "normal", "title": "AI 运营稳定巡检模式"},
                {"created_at": "2026-05-12 11:00:00", "mode": "focus", "title": "AI 运营重点关注模式"},
                {"created_at": "2026-05-12 12:00:00", "mode": "high_alert", "title": "AI 运营高危值班模式"},
            ])
            summary = ArticleHealthService.build_ai_ops_duty_history_summary()

        self.assertEqual(summary["current_mode"], "high_alert")
        self.assertEqual(summary["previous_mode"], "focus")
        self.assertEqual(summary["trend_direction"], "up")

    def test_ai_ops_duty_history_trend_down(self):
        """值班模式严重程度下降时应判定为 down。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_down.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_duty_history([
                {"created_at": "2026-05-12 10:00:00", "mode": "high_alert", "title": "AI 运营高危值班模式"},
                {"created_at": "2026-05-12 11:00:00", "mode": "focus", "title": "AI 运营重点关注模式"},
            ])
            summary = ArticleHealthService.build_ai_ops_duty_history_summary()

        self.assertEqual(summary["trend_direction"], "down")
        self.assertIn("回落", summary["summary"])

    def test_ai_ops_duty_history_trend_stable(self):
        """值班模式严重程度不变时应判定为 stable。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_stable.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_duty_history([
                {"created_at": "2026-05-12 10:00:00", "mode": "normal", "title": "AI 运营稳定巡检模式"},
                {"created_at": "2026-05-12 11:00:00", "mode": "recovery", "title": "AI 运营恢复观察模式"},
            ])
            summary = ArticleHealthService.build_ai_ops_duty_history_summary()

        self.assertEqual(summary["trend_direction"], "stable")

    def test_ai_ops_duty_history_recent_modes(self):
        """值班历史摘要应返回最近模式轨迹。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_recent.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_duty_history([
                {"created_at": "2026-05-12 08:00:00", "mode": "normal", "title": "normal"},
                {"created_at": "2026-05-12 09:00:00", "mode": "recovery", "title": "recovery"},
                {"created_at": "2026-05-12 10:00:00", "mode": "focus", "title": "focus"},
                {"created_at": "2026-05-12 11:00:00", "mode": "high_alert", "title": "high_alert"},
            ])
            summary = ArticleHealthService.build_ai_ops_duty_history_summary()

        self.assertEqual(summary["recent_modes"], ["normal", "recovery", "focus", "high_alert"])

    def test_ai_ops_duty_history_broken_file(self):
        """值班历史文件损坏时应兜底为空列表。"""
        history_path = os.path.join(self.temp_dir.name, "broken_ai_ops_duty_history.json")
        with open(history_path, "w", encoding="utf-8") as history_file:
            history_file.write("{broken")

        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            history = ArticleHealthService._read_ai_ops_duty_history()

        self.assertEqual(history, [])

    def test_ai_ops_duty_history_keeps_latest_100(self):
        """值班历史最多保留最近 100 条。"""
        history_path = os.path.join(self.temp_dir.name, "ai_ops_duty_history_limit.json")
        with patch("services.article_health_service.AI_OPS_DUTY_HISTORY_FILE_PATH", history_path):
            ArticleHealthService._write_ai_ops_duty_history([
                {"created_at": f"2026-05-12 10:{index:02d}:00", "mode": f"mode_{index}", "title": f"title_{index}"}
                for index in range(101)
            ])
            history = ArticleHealthService._read_ai_ops_duty_history()

        self.assertEqual(len(history), 100)
        self.assertEqual(history[0]["mode"], "mode_1")
        self.assertEqual(history[-1]["mode"], "mode_100")

    def test_ai_ops_report_text_includes_duty_history(self):
        """AI 运营日报应包含值班模式变化。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_duty_history_summary": {
                "current_mode": "high_alert",
                "previous_mode": "focus",
                "trend_direction": "up",
                "recent_modes": ["normal", "focus", "high_alert"],
            },
        })

        self.assertIn("值班模式变化", report)
        self.assertIn("当前模式：高危值班", report)
        self.assertIn("上次模式：重点关注", report)
        self.assertIn("正常 → 重点关注 → 高危值班", report)


    def test_ai_ops_timeline_duty_mode_event(self):
        """值班模式升级到 high_alert 时应生成高危时间线事件。"""
        timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_duty_history_summary": {
                "current_mode": "high_alert",
                "trend_direction": "up",
            },
            "ai_ops_score_trend": {"score_change": 0},
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(timeline[0]["type"], "duty_mode")
        self.assertEqual(timeline[0]["level"], "danger")
        self.assertEqual(timeline[0]["title"], "进入 AI 高危值班模式")

    def test_ai_ops_timeline_score_trend_event(self):
        """评分明显变化时应生成评分趋势时间线事件。"""
        down_timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_score_trend": {"score_change": -12},
            "ai_ops_incident_feed": [],
        })
        up_timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_score_trend": {"score_change": 12},
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(down_timeline[0]["title"], "AI 运营评分明显下降")
        self.assertEqual(down_timeline[0]["level"], "danger")
        self.assertEqual(up_timeline[0]["title"], "AI 运营评分明显提升")
        self.assertEqual(up_timeline[0]["level"], "success")

    def test_ai_ops_timeline_merges_incident_feed(self):
        """时间线应合并已有异常播报。"""
        timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_score_trend": {"score_change": 0},
            "ai_ops_incident_feed": [
                {
                    "level": "warning",
                    "title": "连续异常文章较多",
                    "message": "建议优先检查",
                    "created_at": "2026-05-12 10:00:00",
                }
            ],
        })

        self.assertEqual(timeline[0]["type"], "incident")
        self.assertEqual(timeline[0]["title"], "连续异常文章较多")

    def test_ai_ops_timeline_level_sort(self):
        """时间线应按 danger > warning > success > info 排序。"""
        timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_score_trend": {"score_change": 12},
            "ai_ops_incident_feed": [
                {"level": "warning", "title": "warning", "message": "", "created_at": "2026-05-12 10:00:00"},
                {"level": "danger", "title": "danger", "message": "", "created_at": "2026-05-12 10:00:00"},
            ],
        })

        self.assertEqual([item["level"] for item in timeline[:3]], ["danger", "warning", "success"])

    def test_ai_ops_timeline_limit(self):
        """时间线最多返回指定 limit，且最大保护为 50。"""
        timeline = ArticleHealthService.build_ai_ops_timeline({
            "ai_ops_incident_feed": [
                {"level": "info", "title": f"event-{index}", "message": "", "created_at": "2026-05-12 10:00:00"}
                for index in range(60)
            ],
        }, limit=100)

        self.assertEqual(len(timeline), 50)

    def test_ai_ops_timeline_empty_dashboard(self):
        """空 Dashboard 应返回空时间线。"""
        self.assertEqual(ArticleHealthService.build_ai_ops_timeline({}), [])

    def test_ai_ops_report_text_includes_timeline(self):
        """AI 运营日报应包含最近状态时间线。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_timeline": [
                {"level": "danger", "title": "进入 AI 高危值班模式"},
                {"level": "success", "title": "AI 值班模式风险回落"},
            ],
        })

        self.assertIn("最近状态时间线", report)
        self.assertIn("[高风险] 进入 AI 高危值班模式", report)
        self.assertIn("[良好] AI 值班模式风险回落", report)

    def test_ai_ops_health_index_calculation(self):
        """健康指数应综合风险、恢复、趋势和值班模式计算。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 2, "need_attention_articles": 3},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [{}],
            "recent_fail_articles": [{}],
            "trend_summary": {"down_count": 2},
            "ai_ops_score": {"level": "good"},
            "ai_ops_duty_mode": {"mode": "focus"},
        })

        self.assertEqual(result["health_index"], 48)
        self.assertEqual(result["health_level"], "danger")

    def test_ai_ops_health_index_excellent_level(self):
        """高健康指数应判定为 excellent。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 0},
            "ai_ops_score": {"level": "excellent"},
            "ai_ops_duty_mode": {"mode": "normal"},
        })

        self.assertEqual(result["health_index"], 100)
        self.assertEqual(result["health_level"], "excellent")

    def test_ai_ops_health_index_healthy_level(self):
        """75 到 89 的健康指数应判定为 healthy。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 1, "need_attention_articles": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 1},
            "ai_ops_score": {"level": "good"},
            "ai_ops_duty_mode": {"mode": "focus"},
        })

        self.assertEqual(result["health_index"], 83)
        self.assertEqual(result["health_level"], "healthy")

    def test_ai_ops_health_index_warning_level(self):
        """60 到 74 的健康指数应判定为 warning。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 1, "need_attention_articles": 4},
            "persistent_risk_articles": [{}],
            "recovered_articles": [],
            "recent_fail_articles": [{}],
            "trend_summary": {"down_count": 1},
            "ai_ops_score": {"level": "good"},
            "ai_ops_duty_mode": {"mode": "normal"},
        })

        self.assertEqual(result["health_index"], 66)
        self.assertEqual(result["health_level"], "warning")

    def test_ai_ops_health_index_danger_level(self):
        """低于 60 的健康指数应判定为 danger。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 3, "need_attention_articles": 5},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "recent_fail_articles": [{}, {}],
            "trend_summary": {"down_count": 3},
            "ai_ops_score": {"level": "good"},
            "ai_ops_duty_mode": {"mode": "high_alert"},
        })

        self.assertLess(result["health_index"], 60)
        self.assertEqual(result["health_level"], "danger")

    def test_ai_ops_health_index_breakdown(self):
        """健康指数应返回每个加减分项。"""
        result = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 1},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 0},
            "ai_ops_score": {"level": "excellent"},
            "ai_ops_duty_mode": {"mode": "recovery"},
        })
        labels = [item["label"] for item in result["breakdown"]]

        self.assertIn("恢复文章", labels)
        self.assertIn("恢复观察模式", labels)
        self.assertIn("运营评分优秀", labels)
        self.assertIn("无高风险文章", labels)

    def test_ai_ops_health_index_clamped_to_range(self):
        """健康指数应限制在 0 到 100。"""
        low = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 50, "need_attention_articles": 50},
            "persistent_risk_articles": [{} for _ in range(50)],
            "recovered_articles": [],
            "recent_fail_articles": [{} for _ in range(50)],
            "trend_summary": {"down_count": 50},
            "ai_ops_score": {"level": "good"},
            "ai_ops_duty_mode": {"mode": "high_alert"},
        })
        high = ArticleHealthService.build_ai_ops_health_index({
            "summary": {"high_risk_articles": 0, "need_attention_articles": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{} for _ in range(50)],
            "recent_fail_articles": [],
            "trend_summary": {"down_count": 0},
            "ai_ops_score": {"level": "excellent"},
            "ai_ops_duty_mode": {"mode": "recovery"},
        })

        self.assertEqual(low["health_index"], 0)
        self.assertEqual(high["health_index"], 100)

    def test_ai_ops_report_text_includes_health_index(self):
        """AI 运营日报应包含健康指数。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_health_index": {
                "health_index": 78,
                "health_level": "healthy",
                "summary": "当前 AI 运营整体健康，风险可控。",
            },
        })

        self.assertIn("AI 运营健康指数", report)
        self.assertIn("指数：78", report)
        self.assertIn("等级：健康", report)

    def test_ai_ops_health_index_empty_dashboard(self):
        """空 Dashboard 应返回健康指数兜底。"""
        result = ArticleHealthService.build_ai_ops_health_index({})

        self.assertEqual(result["health_index"], 80)
        self.assertEqual(result["health_level"], "healthy")
        self.assertEqual(result["breakdown"], [])


    def test_ai_ops_stability_index_calculation(self):
        """稳定性指数应综合值班、趋势、incident 和连续异常计算。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -12},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [
                {"level": "danger"},
                {"level": "danger"},
                {"level": "warning"},
            ],
        })

        self.assertEqual(result["stability_index"], 38)
        self.assertEqual(result["stability_level"], "unstable")

    def test_ai_ops_stability_index_excellent_level(self):
        """高稳定性指数应判定为 excellent。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["stability_index"], 100)
        self.assertEqual(result["stability_level"], "excellent")

    def test_ai_ops_stability_index_stable_level(self):
        """75 到 89 的稳定性指数应判定为 stable。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "stable"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "warning"}],
        })

        self.assertEqual(result["stability_index"], 86)
        self.assertEqual(result["stability_level"], "stable")

    def test_ai_ops_stability_index_warning_level(self):
        """60 到 74 的稳定性指数应判定为 warning。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [{}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"}],
        })

        self.assertEqual(result["stability_index"], 70)
        self.assertEqual(result["stability_level"], "warning")

    def test_ai_ops_stability_index_unstable_level(self):
        """低于 60 的稳定性指数应判定为 unstable。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -15},
            "persistent_risk_articles": [{}, {}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"} for _ in range(10)],
        })

        self.assertLess(result["stability_index"], 60)
        self.assertEqual(result["stability_level"], "unstable")

    def test_ai_ops_stability_index_breakdown(self):
        """稳定性指数应返回每个加减分项。"""
        result = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })
        labels = [item["label"] for item in result["breakdown"]]

        self.assertIn("恢复观察模式", labels)
        self.assertIn("值班模式风险回落", labels)
        self.assertIn("评分趋势稳定", labels)
        self.assertIn("无 danger 播报", labels)

    def test_ai_ops_stability_index_clamped_to_range(self):
        """稳定性指数应限制在 0 到 100。"""
        low = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -99},
            "persistent_risk_articles": [{} for _ in range(50)],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"} for _ in range(50)],
        })
        high = ArticleHealthService.build_ai_ops_stability_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{} for _ in range(50)],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(low["stability_index"], 0)
        self.assertEqual(high["stability_index"], 100)

    def test_ai_ops_report_text_includes_stability_index(self):
        """AI 运营日报应包含稳定性指数。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_stability_index": {
                "stability_index": 72,
                "stability_level": "stable",
                "summary": "最近 AI 运营整体较稳定。",
            },
        })

        self.assertIn("AI 运营稳定性指数", report)
        self.assertIn("指数：72", report)
        self.assertIn("等级：稳定", report)

    def test_ai_ops_stability_index_empty_dashboard(self):
        """空 Dashboard 应返回稳定性指数兜底。"""
        result = ArticleHealthService.build_ai_ops_stability_index({})

        self.assertEqual(result["stability_index"], 80)
        self.assertEqual(result["stability_level"], "stable")
        self.assertEqual(result["breakdown"], [])


    def test_ai_ops_volatility_index_calculation(self):
        """波动指数应综合值班切换、评分变化、incident 和连续异常计算。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {
                "trend_direction": "up",
                "recent_modes": ["normal", "focus", "high_alert"],
            },
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -12},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [
                {"level": "danger"},
                {"level": "danger"},
                {"level": "warning"},
            ],
        })

        self.assertEqual(result["volatility_index"], 90)
        self.assertEqual(result["volatility_level"], "highly_volatile")

    def test_ai_ops_volatility_index_very_stable_level(self):
        """低于 20 的波动指数应判定为 very_stable。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down", "recent_modes": ["focus", "recovery"]},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{}, {}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["volatility_index"], 0)
        self.assertEqual(result["volatility_level"], "very_stable")

    def test_ai_ops_volatility_index_stable_level(self):
        """20 到 39 的波动指数应判定为 stable。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "stable", "recent_modes": ["focus"]},
            "ai_ops_score_trend": {"trend_direction": "up", "score_change": 20},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["volatility_index"], 25)
        self.assertEqual(result["volatility_level"], "stable")

    def test_ai_ops_volatility_index_volatile_level(self):
        """40 到 69 的波动指数应判定为 volatile。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "up", "recent_modes": ["normal", "focus"]},
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -12},
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "warning"}, {"level": "warning"}],
        })

        self.assertEqual(result["volatility_index"], 41)
        self.assertEqual(result["volatility_level"], "volatile")

    def test_ai_ops_volatility_index_highly_volatile_level(self):
        """大于等于 70 的波动指数应判定为 highly_volatile。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {
                "trend_direction": "up",
                "recent_modes": ["normal", "focus", "normal", "focus", "high_alert"],
            },
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -20},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"} for _ in range(3)],
        })

        self.assertGreaterEqual(result["volatility_index"], 70)
        self.assertEqual(result["volatility_level"], "highly_volatile")

    def test_ai_ops_volatility_index_breakdown(self):
        """波动指数应返回每个加减分项。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down", "recent_modes": ["normal", "focus", "recovery"]},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })
        labels = [item["label"] for item in result["breakdown"]]

        self.assertIn("恢复观察模式", labels)
        self.assertIn("值班模式风险回落", labels)
        self.assertIn("值班模式切换频繁", labels)
        self.assertIn("评分趋势稳定", labels)
        self.assertIn("无 danger 播报", labels)

    def test_ai_ops_volatility_index_clamped_to_range(self):
        """波动指数应限制在 0 到 100。"""
        low = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down", "recent_modes": ["recovery"]},
            "ai_ops_score_trend": {"trend_direction": "stable", "score_change": 0},
            "persistent_risk_articles": [],
            "recovered_articles": [{} for _ in range(50)],
            "ai_ops_incident_feed": [],
        })
        high = ArticleHealthService.build_ai_ops_volatility_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {
                "trend_direction": "up",
                "recent_modes": ["normal", "focus", "normal", "focus", "normal", "high_alert"],
            },
            "ai_ops_score_trend": {"trend_direction": "down", "score_change": -99},
            "persistent_risk_articles": [{} for _ in range(50)],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"} for _ in range(50)],
        })

        self.assertEqual(low["volatility_index"], 0)
        self.assertEqual(high["volatility_index"], 100)

    def test_ai_ops_report_text_includes_volatility_index(self):
        """AI 运营日报应包含波动指数。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_volatility_index": {
                "volatility_index": 68,
                "volatility_level": "volatile",
                "summary": "最近 AI 运营存在一定波动。",
            },
        })

        self.assertIn("AI 运营波动指数", report)
        self.assertIn("指数：68", report)
        self.assertIn("等级：波动", report)

    def test_ai_ops_volatility_index_empty_dashboard(self):
        """空 Dashboard 应返回波动指数兜底。"""
        result = ArticleHealthService.build_ai_ops_volatility_index({})

        self.assertEqual(result["volatility_index"], 20)
        self.assertEqual(result["volatility_level"], "stable")
        self.assertEqual(result["breakdown"], [])

    def test_ai_ops_recovery_index_calculation(self):
        """恢复力指数应综合恢复文章、值班回落、评分提升和风险项计算。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"trend_direction": "up", "score_change": 12},
            "ai_ops_score": {"level": "good"},
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}, {}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["recovery_index"], 100)
        self.assertEqual(result["recovery_level"], "excellent")

    def test_ai_ops_recovery_index_excellent_level(self):
        """90 以上的恢复力指数应判定为 excellent。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"score_change": 10},
            "ai_ops_score": {"level": "excellent"},
            "persistent_risk_articles": [],
            "recovered_articles": [{}, {}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["recovery_index"], 100)
        self.assertEqual(result["recovery_level"], "excellent")

    def test_ai_ops_recovery_index_normal_mode_can_reach_excellent(self):
        """75 到 89 的恢复力指数应判定为 strong。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "normal"},
            "ai_ops_duty_history_summary": {"trend_direction": "stable"},
            "ai_ops_score_trend": {"score_change": 0},
            "ai_ops_score": {"level": "good"},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["recovery_index"], 96)
        self.assertEqual(result["recovery_level"], "excellent")

    def test_ai_ops_recovery_index_strong_level_with_focus_mode(self):
        """focus 模式下存在恢复文章时，恢复力指数应落入 strong 区间。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "focus"},
            "ai_ops_duty_history_summary": {"trend_direction": "stable"},
            "ai_ops_score_trend": {"score_change": 0},
            "ai_ops_score": {"level": "good"},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["recovery_index"], 76)
        self.assertEqual(result["recovery_level"], "strong")

    def test_ai_ops_recovery_index_normal_level(self):
        """60 到 74 的恢复力指数应判定为 normal。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "normal"},
            "ai_ops_duty_history_summary": {"trend_direction": "stable"},
            "ai_ops_score_trend": {"score_change": 0},
            "ai_ops_score": {"level": "good"},
            "persistent_risk_articles": [{}],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(result["recovery_index"], 68)
        self.assertEqual(result["recovery_level"], "normal")

    def test_ai_ops_recovery_index_weak_level(self):
        """低于 60 的恢复力指数应判定为 weak。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"score_change": -12},
            "ai_ops_score": {"level": "danger"},
            "persistent_risk_articles": [{}, {}],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"}, {"level": "danger"}],
        })

        self.assertLess(result["recovery_index"], 60)
        self.assertEqual(result["recovery_level"], "weak")

    def test_ai_ops_recovery_index_breakdown(self):
        """恢复力指数应返回每个加减分项。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"score_change": 12},
            "ai_ops_score": {"level": "excellent"},
            "persistent_risk_articles": [],
            "recovered_articles": [{}],
            "ai_ops_incident_feed": [],
        })
        labels = [item["label"] for item in result["breakdown"]]

        self.assertIn("恢复文章", labels)
        self.assertIn("恢复文章多于连续异常", labels)
        self.assertIn("恢复观察模式", labels)
        self.assertIn("值班模式风险回落", labels)
        self.assertIn("运营评分明显提升", labels)
        self.assertIn("无 danger 播报", labels)

    def test_ai_ops_recovery_index_clamped_to_range(self):
        """恢复力指数应限制在 0 到 100。"""
        low = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "high_alert"},
            "ai_ops_duty_history_summary": {"trend_direction": "up"},
            "ai_ops_score_trend": {"score_change": -99},
            "ai_ops_score": {"level": "danger"},
            "persistent_risk_articles": [{} for _ in range(50)],
            "recovered_articles": [],
            "ai_ops_incident_feed": [{"level": "danger"} for _ in range(50)],
        })
        high = ArticleHealthService.build_ai_ops_recovery_index({
            "ai_ops_duty_mode": {"mode": "recovery"},
            "ai_ops_duty_history_summary": {"trend_direction": "down"},
            "ai_ops_score_trend": {"score_change": 99},
            "ai_ops_score": {"level": "excellent"},
            "persistent_risk_articles": [],
            "recovered_articles": [{} for _ in range(50)],
            "ai_ops_incident_feed": [],
        })

        self.assertEqual(low["recovery_index"], 0)
        self.assertEqual(high["recovery_index"], 100)

    def test_ai_ops_report_text_includes_recovery_index(self):
        """AI 运营日报应包含恢复力指数。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营整体稳定"},
            "ai_ops_recovery_index": {
                "recovery_index": 82,
                "recovery_level": "strong",
                "summary": "当前 AI 运营恢复能力较强。",
            },
        })

        self.assertIn("AI 运营恢复力指数", report)
        self.assertIn("指数：82", report)
        self.assertIn("等级：强", report)

    def test_ai_ops_recovery_index_empty_dashboard(self):
        """空 Dashboard 应返回恢复力指数兜底。"""
        result = ArticleHealthService.build_ai_ops_recovery_index({})

        self.assertEqual(result["recovery_index"], 60)
        self.assertEqual(result["recovery_level"], "normal")
        self.assertEqual(result["breakdown"], [])


    def test_ai_ops_playbook_continuous_preflight_failure(self):
        """连续终检失败应生成 critical 处置建议。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{
                "article_id": 1,
                "title": "文章A",
                "risk_tags": ["连续终检失败"],
            }],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_preflight_failure")
        self.assertEqual(playbook["priority"], "critical")
        self.assertTrue(playbook["should_manual_review"])
        self.assertTrue(playbook["should_pause_publish"])
        self.assertIn("检查 CTA 卡片", playbook["recommended_actions"])

    def test_ai_ops_playbook_continuous_publish_failure(self):
        """连续发布失败应生成微信链路排查建议。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{
                "article_id": 2,
                "title": "文章B",
                "risk_tags": ["连续发布失败"],
            }],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_publish_failure")
        self.assertEqual(playbook["priority"], "critical")
        self.assertIn("微信 token", playbook["root_causes"])
        self.assertIn("检查 media_id", playbook["recommended_actions"])

    def test_ai_ops_playbook_continuous_high_risk(self):
        """连续高风险应生成内容质量处置建议。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{
                "article_id": 3,
                "title": "文章C",
                "risk_tags": ["连续高风险"],
            }],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_high_risk")
        self.assertEqual(playbook["priority"], "high")
        self.assertIn("AI 内容质量下降", playbook["root_causes"])
        self.assertIn("检查提示词", playbook["recommended_actions"])

    def test_ai_ops_playbook_high_volatility(self):
        """高度波动应生成高优先级 playbook。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
            "ai_ops_priority_queue": [{"article_id": 4, "title": "文章D"}],
        })

        playbook = next(item for item in result if item["type"] == "high_volatility")
        self.assertEqual(playbook["priority"], "high")
        self.assertTrue(playbook["should_pause_publish"])
        self.assertIn("暂停批量发布", playbook["recommended_actions"])

    def test_ai_ops_playbook_good_recovery(self):
        """恢复文章不少于连续异常时应生成 success playbook。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{"article_id": 1, "risk_tags": ["连续高风险"]}],
            "recovered_articles": [
                {"article_id": 5, "title": "文章E"},
                {"article_id": 6, "title": "文章F"},
            ],
        })

        playbook = next(item for item in result if item["type"] == "good_recovery")
        self.assertEqual(playbook["level"], "success")
        self.assertFalse(playbook["should_pause_publish"])

    def test_ai_ops_playbook_sorting(self):
        """Playbook 应按 critical > high > medium > low 排序。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [
                {"article_id": 1, "title": "A", "risk_tags": ["连续高风险"]},
                {"article_id": 2, "title": "B", "risk_tags": ["连续终检失败"]},
            ],
            "recovered_articles": [{"article_id": 3, "title": "C"}],
            "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
        })

        self.assertEqual(result[0]["priority"], "critical")
        self.assertEqual(result[0]["type"], "continuous_preflight_failure")

    def test_ai_ops_playbook_limit(self):
        """Playbook 最多返回 10 条。"""
        dashboard = {
            "persistent_risk_articles": [
                {"article_id": idx, "title": f"文章{idx}", "risk_tags": ["连续终检失败", "连续发布失败", "连续高风险"]}
                for idx in range(20)
            ],
            "recovered_articles": [{"article_id": idx, "title": f"文章{idx}"} for idx in range(20)],
            "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
        }

        result = ArticleHealthService.build_ai_ops_playbooks(dashboard, limit=50)

        self.assertLessEqual(len(result), 10)

    def test_ai_ops_playbook_empty_data(self):
        """空 Dashboard 不生成 playbook。"""
        self.assertEqual(ArticleHealthService.build_ai_ops_playbooks({}), [])

    def test_ai_ops_report_text_includes_playbooks(self):
        """日报文案应包含处置建议。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营稳定"},
            "ai_ops_playbooks": [{
                "title": "连续终检失败",
                "recommended_actions": ["检查 CTA", "检查 HTML", "人工复核"],
            }],
        })

        self.assertIn("今日重点处置建议", report)
        self.assertIn("1. 连续终检失败", report)
        self.assertIn("* 检查 CTA", report)

    def test_ai_ops_playbook_generates_actions(self):
        """有 related_articles 时应生成查看文章、重新终检、重新决策动作。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{
                "article_id": 10,
                "title": "文章A",
                "risk_tags": ["连续终检失败"],
            }],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_preflight_failure")
        action_types = [item["action_type"] for item in playbook["actions"]]

        self.assertIn("open_article", action_types)
        self.assertIn("rerun_preflight", action_types)
        self.assertIn("rerun_decision", action_types)

    def test_ai_ops_playbook_empty_related_articles_has_no_actions(self):
        """没有 related_articles 时 actions 应为空。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
            "ai_ops_priority_queue": [],
        })

        playbook = next(item for item in result if item["type"] == "high_volatility")

        self.assertEqual(playbook["actions"], [])

    def test_ai_ops_playbook_actions_limit_first_three_articles(self):
        """actions 最多覆盖前 3 篇关联文章。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [
                {"article_id": idx, "title": f"文章{idx}", "risk_tags": ["连续终检失败"]}
                for idx in range(1, 6)
            ],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_preflight_failure")
        article_ids = sorted({item["article_id"] for item in playbook["actions"]})

        self.assertEqual(article_ids, [1, 2, 3])
        self.assertEqual(len(playbook["actions"]), 9)

    def test_ai_ops_playbook_action_fields_complete(self):
        """action 字段应包含前端执行所需参数。"""
        result = ArticleHealthService.build_ai_ops_playbooks({
            "persistent_risk_articles": [{
                "article_id": 7,
                "title": "文章A",
                "risk_tags": ["连续发布失败"],
            }],
            "recovered_articles": [],
        })

        playbook = next(item for item in result if item["type"] == "continuous_publish_failure")
        action = next(item for item in playbook["actions"] if item["action_type"] == "rerun_preflight")

        self.assertEqual(action["label"], "重新终检")
        self.assertEqual(action["method"], "POST")
        self.assertEqual(action["url"], "/ai-dashboard/playbook-action")
        self.assertEqual(action["article_id"], 7)
        self.assertIn("AI 发布前终检", action["confirm_text"])

    def test_ai_root_cause_preflight_failure_cluster(self):
        """连续终检失败文章集中时应识别终检失败根因。"""
        with patch.object(ArticleHealthService, "_build_root_cause_top_templates", return_value=[]):
            result = ArticleHealthService.build_ai_root_cause_analysis({
                "persistent_risk_articles": [
                    {"article_id": 1, "title": "文章A", "risk_tags": ["连续终检失败"]},
                    {"article_id": 2, "title": "文章B", "risk_tags": ["连续终检失败"]},
                ],
            })

        cause = next(item for item in result["root_causes"] if item["type"] == "preflight_failure_cluster")

        self.assertEqual(cause["level"], "danger")
        self.assertIn("检查 CTA 卡片结构", cause["recommended_actions"])
        self.assertIn("连续终检失败", [item["pattern"] for item in result["top_failure_patterns"]])

    def test_ai_root_cause_publish_failure_cluster(self):
        """最近发布失败集中或连续发布失败时应识别发布失败根因。"""
        with patch.object(ArticleHealthService, "_build_root_cause_top_templates", return_value=[]):
            result = ArticleHealthService.build_ai_root_cause_analysis({
                "recent_fail_articles": [
                    {"article_id": 1, "title": "文章A"},
                    {"article_id": 2, "title": "文章B"},
                    {"article_id": 3, "title": "文章C"},
                ],
                "persistent_risk_articles": [],
            })

        cause = next(item for item in result["root_causes"] if item["type"] == "publish_failure_cluster")

        self.assertEqual(cause["level"], "danger")
        self.assertIn("检查 access_token 获取", cause["recommended_actions"])

    def test_ai_root_cause_high_risk_content_cluster(self):
        """高风险文章集中时应识别内容风险根因。"""
        with patch.object(ArticleHealthService, "_build_root_cause_top_templates", return_value=[]):
            result = ArticleHealthService.build_ai_root_cause_analysis({
                "summary": {"high_risk_articles": 3},
                "persistent_risk_articles": [],
            })

        cause = next(item for item in result["root_causes"] if item["type"] == "high_risk_content_cluster")

        self.assertEqual(cause["level"], "warning")
        self.assertIn("降低营销承诺语气", cause["recommended_actions"])

    def test_ai_root_cause_ops_score_drop(self):
        """AI 运营评分明显下降时应识别评分下降根因。"""
        with patch.object(ArticleHealthService, "_build_root_cause_top_templates", return_value=[]):
            result = ArticleHealthService.build_ai_root_cause_analysis({
                "ai_ops_score_trend": {"score_change": -12, "current_score": 68},
                "persistent_risk_articles": [],
            })

        cause = next(item for item in result["root_causes"] if item["type"] == "ops_score_drop")

        self.assertEqual(cause["title"], "AI 运营评分明显下降")
        self.assertIn("查看异常播报", cause["recommended_actions"])

    def test_ai_root_cause_volatile_ops_state(self):
        """高波动或不稳定状态应识别运营状态波动根因。"""
        with patch.object(ArticleHealthService, "_build_root_cause_top_templates", return_value=[]):
            result = ArticleHealthService.build_ai_root_cause_analysis({
                "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
                "ai_ops_stability_index": {"stability_level": "stable"},
                "persistent_risk_articles": [],
            })

        cause = next(item for item in result["root_causes"] if item["type"] == "volatile_ops_state")

        self.assertEqual(cause["title"], "AI 运营状态波动较大")
        self.assertIn("暂停批量发布", cause["recommended_actions"])

    def test_ai_root_cause_top_failure_patterns(self):
        """失败模式排行应统计终检、发布、高风险、评分下降和高波动。"""
        result = ArticleHealthService._build_top_failure_patterns(
            {
                "summary": {"high_risk_articles": 4},
                "recent_fail_articles": [{"article_id": 1}, {"article_id": 2}],
                "ai_ops_score_trend": {"score_change": -15},
                "ai_ops_volatility_index": {"volatility_level": "highly_volatile"},
            },
            preflight_count=2,
            publish_count=1,
            high_risk_count=3,
        )
        patterns = {item["pattern"]: item["count"] for item in result}

        self.assertEqual(patterns["连续终检失败"], 2)
        self.assertEqual(patterns["连续发布失败"], 1)
        self.assertEqual(patterns["AI 评分下降"], 1)
        self.assertEqual(patterns["高波动"], 1)

    def test_ai_root_cause_top_templates_missing_fields(self):
        """articles 表没有模板字段时，模板聚合应安全返回空列表。"""
        class FakeConn:
            def execute(self, _sql):
                return self

            def fetchall(self):
                return [{"id": 1, "title": "无模板字段文章"}]

            def close(self):
                return None

        with patch("services.article_health_service.get_db", return_value=FakeConn()):
            result = ArticleHealthService._build_root_cause_top_templates({})

        self.assertEqual(result, [])

    def test_ai_root_cause_recommended_actions_deduplicated(self):
        """根因推荐动作应去重并保持顺序。"""
        result = ArticleHealthService._collect_root_cause_actions([
            {"recommended_actions": ["检查 CTA 卡片结构", "检查 HTML 清洗逻辑"]},
            {"recommended_actions": ["检查 HTML 清洗逻辑", "检查微信不兼容标签"]},
        ])

        self.assertEqual(result.count("检查 HTML 清洗逻辑"), 1)
        self.assertEqual(result[0], "检查 CTA 卡片结构")

    def test_ai_root_cause_empty_fallback(self):
        """无集中根因时应返回兜底摘要。"""
        result = ArticleHealthService.build_ai_root_cause_analysis({})

        self.assertEqual(result["root_causes"], [])
        self.assertIn("当前暂无明显集中性根因", result["summary"])

    def test_ai_ops_report_text_includes_root_cause_analysis(self):
        """日报文案应包含根因分析板块。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营稳定"},
            "ai_root_cause_analysis": {
                "summary": "当前 AI 运营风险主要集中在：终检失败集中出现，建议优先处理。",
                "recommended_actions": ["检查 CTA 卡片结构", "检查微信 token"],
            },
        })

        self.assertIn("根因分析", report)
        self.assertIn("终检失败集中出现", report)
        self.assertIn("检查 CTA 卡片结构", report)

    def _patch_template_ops_fixture(self):
        articles = [
            {"id": 1, "title": "A1", "template_name": "企业融资模板"},
            {"id": 2, "title": "A2", "template_name": "企业融资模板"},
            {"id": 3, "title": "B1", "template_title": "企业现金流模板"},
            {"id": 4, "title": "B2", "template_title": "企业现金流模板"},
            {"id": 5, "title": "C1", "article_template_name": "波动模板"},
        ]
        health_map = {
            1: {"score": 40, "risk_level": "high"},
            2: {"score": 70, "risk_level": "medium"},
            3: {"score": 90, "risk_level": "low"},
            4: {"score": 86, "risk_level": "low"},
            5: {"score": 65, "risk_level": "medium"},
        }
        trend_map = {
            1: {"score_change": -20, "trend_direction": "down"},
            2: {"score_change": -5, "trend_direction": "stable"},
            3: {"score_change": 10, "trend_direction": "up"},
            4: {"score_change": 0, "trend_direction": "stable"},
            5: {"score_change": -50, "trend_direction": "down"},
        }
        logs_map = {
            1: [
                {"action_type": "ai_preflight", "result_json": json.dumps({"pass_preflight": False})},
                {"action_type": "ai_preflight", "result_json": json.dumps({"pass_preflight": False})},
            ],
        }
        tasks_map = {
            1: [{"status": "failed"}, {"status": "failed"}, {"status": "failed"}],
        }
        return (
            patch.object(ArticleHealthService, "_list_articles_with_template_fields", return_value=articles),
            patch.object(ArticleHealthService, "_list_ai_logs", side_effect=lambda article_id, limit=10: logs_map.get(article_id, [])),
            patch.object(ArticleHealthService, "_list_publish_tasks", side_effect=lambda article_id, limit=10: tasks_map.get(article_id, [])),
            patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map.get(article_id, {})),
            patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map.get(article_id, {})),
        )

    def test_template_ops_template_health_generated(self):
        """模板健康聚合应生成文章数、风险数、终检失败、发布失败和状态。"""
        patches = self._patch_template_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleHealthService.build_template_ops_analysis({})

        template = next(item for item in result["template_health"] if item["template"] == "企业融资模板")

        self.assertEqual(template["article_count"], 2)
        self.assertEqual(template["high_risk_count"], 1)
        self.assertEqual(template["preflight_fail_count"], 2)
        self.assertEqual(template["publish_fail_count"], 3)
        self.assertEqual(template["status"], "danger")

    def test_template_ops_high_risk_templates(self):
        """危险模板应进入 high_risk_templates。"""
        patches = self._patch_template_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleHealthService.build_template_ops_analysis({})

        names = [item["template"] for item in result["high_risk_templates"]]

        self.assertIn("企业融资模板", names)

    def test_template_ops_unstable_templates(self):
        """平均波动高或稳定性低的模板应进入 unstable_templates。"""
        patches = self._patch_template_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleHealthService.build_template_ops_analysis({})

        names = [item["template"] for item in result["unstable_templates"]]

        self.assertIn("波动模板", names)

    def test_template_ops_recovery_templates(self):
        """低风险、高健康分、高稳定性的模板应进入恢复优秀列表。"""
        patches = self._patch_template_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleHealthService.build_template_ops_analysis({})

        names = [item["template"] for item in result["template_recovery"]]

        self.assertIn("企业现金流模板", names)

    def test_template_ops_missing_template_fields_fallback(self):
        """缺失模板字段时应返回空分析，不影响 Dashboard。"""
        with patch.object(ArticleHealthService, "_list_articles_with_template_fields", return_value=[]):
            result = ArticleHealthService.build_template_ops_analysis({})

        self.assertEqual(result["template_health"], [])
        self.assertIn("暂无法生成模板级运营分析", result["summary"])

    def test_template_ops_summary(self):
        """模板运营 summary 应同时说明风险集中和恢复优秀模板。"""
        patches = self._patch_template_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleHealthService.build_template_ops_analysis({})

        self.assertIn("企业融资模板", result["summary"])
        self.assertIn("企业现金流模板", result["summary"])

    def test_template_ops_recommended_actions_deduplicated(self):
        """模板运营推荐动作应去重并限制长度。"""
        actions = ArticleHealthService._build_template_ops_actions(
            high_risk_templates=[{"template": "A"}],
            unstable_templates=[{"template": "A"}],
        )

        self.assertEqual(len(actions), len(set(actions)))
        self.assertLessEqual(len(actions), 8)
        self.assertIn("检查高风险模板提示词", actions)
        self.assertIn("优化 CTA 结构", actions)

    def test_ai_ops_report_text_includes_template_ops_analysis(self):
        """日报文案应包含模板运营分析板块。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营稳定"},
            "template_ops_analysis": {
                "summary": "当前风险主要集中在：企业融资模板。",
                "high_risk_templates": [{"template": "企业融资模板"}],
                "template_recovery": [{"template": "企业现金流模板"}],
                "recommended_actions": ["检查高风险模板提示词", "优化 CTA 结构"],
            },
        })

        self.assertIn("模板运营分析", report)
        self.assertIn("企业融资模板", report)
        self.assertIn("检查高风险模板提示词", report)

    def _patch_prompt_ops_fixture(self):
        articles = [
            {"id": 1, "title": "A1", "prompt_name": "企业融资规划"},
            {"id": 2, "title": "A2", "prompt_name": "企业融资规划"},
            {"id": 3, "title": "B1", "category": "知识科普"},
            {"id": 4, "title": "B2", "category": "知识科普"},
            {"id": 5, "title": "C1", "writing_mode": "热点解读"},
        ]
        health_map = {
            1: {"score": 42, "risk_level": "high"},
            2: {"score": 68, "risk_level": "medium"},
            3: {"score": 88, "risk_level": "low"},
            4: {"score": 84, "risk_level": "low"},
            5: {"score": 62, "risk_level": "medium"},
        }
        trend_map = {
            1: {"score_change": -20, "trend_direction": "down"},
            2: {"score_change": -8, "trend_direction": "stable"},
            3: {"score_change": 0, "trend_direction": "stable"},
            4: {"score_change": 5, "trend_direction": "up"},
            5: {"score_change": -55, "trend_direction": "down"},
        }
        logs_map = {
            1: [
                {"action_type": "ai_preflight", "result_json": json.dumps({"pass_preflight": False})},
                {"action_type": "ai_preflight", "result_json": json.dumps({"pass_preflight": False})},
            ],
        }
        tasks_map = {
            1: [{"status": "failed"}, {"status": "failed"}, {"status": "failed"}],
        }
        return (
            patch.object(ArticleHealthService, "_list_articles_with_prompt_fields", return_value=articles),
            patch.object(ArticleHealthService, "_load_prompt_template_lookup", return_value={}),
            patch.object(ArticleHealthService, "_list_ai_logs", side_effect=lambda article_id, limit=10: logs_map.get(article_id, [])),
            patch.object(ArticleHealthService, "_list_publish_tasks", side_effect=lambda article_id, limit=10: tasks_map.get(article_id, [])),
            patch.object(ArticleHealthService, "build_article_health", side_effect=lambda article_id: health_map.get(article_id, {})),
            patch.object(ArticleHealthService, "build_health_trend", side_effect=lambda article_id: trend_map.get(article_id, {})),
        )

    def test_prompt_ops_prompt_health_generated(self):
        """提示词健康聚合应生成风险率、失败率和状态。"""
        patches = self._patch_prompt_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = ArticleHealthService.build_prompt_ops_analysis({})

        prompt = next(item for item in result["prompt_health"] if item["prompt"] == "企业融资规划")

        self.assertEqual(prompt["article_count"], 2)
        self.assertEqual(prompt["high_risk_count"], 1)
        self.assertEqual(prompt["preflight_fail_count"], 2)
        self.assertEqual(prompt["publish_fail_count"], 3)
        self.assertEqual(prompt["status"], "danger")

    def test_prompt_ops_high_risk_prompts(self):
        """危险提示词应进入 high_risk_prompts。"""
        patches = self._patch_prompt_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = ArticleHealthService.build_prompt_ops_analysis({})

        names = [item["prompt"] for item in result["high_risk_prompts"]]

        self.assertIn("企业融资规划", names)

    def test_prompt_ops_unstable_prompts(self):
        """高波动提示词应进入 unstable_prompts。"""
        patches = self._patch_prompt_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = ArticleHealthService.build_prompt_ops_analysis({})

        names = [item["prompt"] for item in result["unstable_prompts"]]

        self.assertIn("热点解读", names)

    def test_prompt_ops_recommendations_generated(self):
        """提示词推荐应覆盖高风险、终检失败、发布失败和波动问题。"""
        patches = self._patch_prompt_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = ArticleHealthService.build_prompt_ops_analysis({})

        issues = [item["issue"] for item in result["prompt_recommendations"]]

        self.assertIn("高风险率偏高", issues)
        self.assertIn("终检失败偏高", issues)
        self.assertIn("发布失败偏高", issues)
        self.assertIn("波动过高", issues)

    def test_prompt_ops_missing_prompt_fields_fallback(self):
        """缺失提示词字段时应返回空分析。"""
        with patch.object(ArticleHealthService, "_list_articles_with_prompt_fields", return_value=[]):
            result = ArticleHealthService.build_prompt_ops_analysis({})

        self.assertEqual(result["prompt_health"], [])
        self.assertIn("当前暂无可用于提示词分析的字段", result["summary"])

    def test_prompt_ops_summary(self):
        """提示词 summary 应说明风险集中提示词。"""
        patches = self._patch_prompt_ops_fixture()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = ArticleHealthService.build_prompt_ops_analysis({})

        self.assertIn("企业融资规划", result["summary"])

    def test_prompt_ops_recommended_actions_deduplicated(self):
        """提示词推荐动作应去重并限制长度。"""
        actions = ArticleHealthService._build_prompt_ops_actions([
            {"issue": "高风险率偏高"},
            {"issue": "高风险率偏高"},
            {"issue": "终检失败偏高"},
            {"issue": "波动过高"},
        ])

        self.assertEqual(len(actions), len(set(actions)))
        self.assertLessEqual(len(actions), 8)
        self.assertIn("优化高风险提示词的合规表达", actions)
        self.assertIn("增加微信兼容性约束", actions)

    def test_ai_ops_report_text_includes_prompt_ops_analysis(self):
        """日报文案应包含提示词运营分析板块。"""
        report = ArticleHealthService.build_ai_ops_report_text({
            "daily_ai_ops_summary": {"title": "今日 AI 运营稳定"},
            "prompt_ops_analysis": {
                "summary": "当前提示词风险主要集中在：企业融资规划。",
                "high_risk_prompts": [{"prompt": "企业融资规划"}],
                "unstable_prompts": [{"prompt": "热点解读"}],
                "recommended_actions": ["降低营销承诺语气", "增加微信兼容性约束"],
            },
        })

        self.assertIn("提示词运营分析", report)
        self.assertIn("企业融资规划", report)
        self.assertIn("增加微信兼容性约束", report)


if __name__ == "__main__":
    unittest.main()
