import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.ai_operation_log_service import AIOperationLogService


class AIOperationLogServiceTestCase(unittest.TestCase):
    """AI 操作日志服务测试。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "ai_logs_test.db")
        self._create_schema()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_schema(self):
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE ai_operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                agent_name TEXT,
                action_type TEXT,
                operator_id INTEGER,
                operator_name TEXT,
                ok INTEGER DEFAULT 0,
                summary TEXT,
                result_json TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    def _patch_db(self):
        return patch.multiple(
            "services.ai_operation_log_service",
            get_db=self._connect,
            is_mysql=lambda: False,
        )

    def test_create_log_success(self):
        """create_log 应能成功写入日志并返回 ID。"""
        with self._patch_db():
            log_id = AIOperationLogService.create_log(
                1,
                "ArticleReviewAgent",
                "ai_review",
                {"ok": True, "risk_level": "low", "can_publish": True},
                operator_name="admin",
            )

        self.assertIsNotNone(log_id)
        conn = self._connect()
        row = conn.execute("SELECT * FROM ai_operation_logs WHERE id=?", (log_id,)).fetchone()
        conn.close()
        self.assertEqual(row["article_id"], 1)
        self.assertEqual(row["ok"], 1)
        self.assertIn("风险等级：low", row["summary"])

    def test_list_logs_for_article_order_by_id_desc(self):
        """list_logs_for_article 应按 id 倒序返回。"""
        with self._patch_db():
            first_id = AIOperationLogService.create_log(1, "AgentA", "ai_review", {"ok": True})
            second_id = AIOperationLogService.create_log(1, "AgentB", "ai_workflow", {"ok": True})

            logs = AIOperationLogService.list_logs_for_article(1, limit=20)

        self.assertEqual([log["id"] for log in logs], [second_id, first_id])

    def test_build_summary_for_ai_review(self):
        """ai_review 摘要应包含风险等级和建议发布状态。"""
        summary = AIOperationLogService.build_summary(
            "ai_review",
            {"ok": True, "risk_level": "medium", "can_publish": False},
        )
        self.assertEqual(summary, "风险等级：medium，建议发布：否")

    def test_build_summary_for_ai_rewrite(self):
        """ai_rewrite 摘要应包含优化稿标题。"""
        summary = AIOperationLogService.build_summary(
            "ai_rewrite",
            {"ok": True, "rewritten_title": "企业融资前先看这三点"},
        )
        self.assertIn("已生成优化稿", summary)
        self.assertIn("企业融资前先看这三点", summary)

    def test_build_summary_for_ai_preflight(self):
        """ai_preflight 摘要应包含终检结果和风险等级。"""
        summary = AIOperationLogService.build_summary(
            "ai_preflight",
            {"ok": True, "pass_preflight": True, "risk_level": "low"},
        )
        self.assertEqual(summary, "终检通过：是，风险等级：low")

    def test_build_summary_for_ai_decision(self):
        """ai_decision 摘要应包含中文决策文案。"""
        summary = AIOperationLogService.build_summary(
            "ai_decision",
            {"ok": True, "decision_label": "建议推送微信草稿箱"},
        )
        self.assertEqual(summary, "决策：建议推送微信草稿箱")

    def test_result_json_preserves_chinese(self):
        """result_json 应使用 ensure_ascii=False 保存中文。"""
        with self._patch_db():
            log_id = AIOperationLogService.create_log(
                2,
                "ArticleService",
                "apply_ai_rewrite",
                {"ok": True, "msg": "已应用 AI 优化稿", "title": "中文标题"},
            )

        conn = self._connect()
        row = conn.execute("SELECT result_json FROM ai_operation_logs WHERE id=?", (log_id,)).fetchone()
        conn.close()
        self.assertIn("中文标题", row["result_json"])

    def test_create_log_exception_does_not_raise(self):
        """日志写入异常应返回 None，不影响主流程。"""
        with patch("services.ai_operation_log_service.get_db", side_effect=RuntimeError("db down")):
            log_id = AIOperationLogService.create_log(1, "Agent", "ai_review", {"ok": True})
        self.assertIsNone(log_id)


if __name__ == "__main__":
    unittest.main()
