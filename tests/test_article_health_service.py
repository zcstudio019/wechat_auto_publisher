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

    def _insert_article(self):
        conn = self._connect()
        conn.execute("INSERT INTO articles (id, title, status) VALUES (?, ?, ?)", (self.article_id, "测试文章", "draft"))
        conn.commit()
        conn.close()

    def _insert_log(self, action_type, result, hours_ago=0):
        created_at = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO ai_operation_logs (article_id, action_type, ok, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (self.article_id, action_type, 1 if result.get("ok", True) else 0, json.dumps(result, ensure_ascii=False), created_at),
        )
        conn.commit()
        conn.close()

    def _insert_publish_task(self, status):
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO publish_tasks (article_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (self.article_id, status, now_text, now_text),
        )
        conn.commit()
        conn.close()

    def _build_health(self):
        with self._patch_db():
            return ArticleHealthService.build_article_health(self.article_id)

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


if __name__ == "__main__":
    unittest.main()
