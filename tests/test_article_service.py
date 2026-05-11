import unittest
from unittest.mock import patch

import services.article_service as article_service_module
from services.article_service import ArticleService


class _FakeCursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, article_exists=True):
        self.article_exists = article_exists
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if sql.strip().upper().startswith("SELECT"):
            return _FakeCursor({"id": 1} if self.article_exists else None)
        return _FakeCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class ArticleServiceTestCase(unittest.TestCase):
    def _valid_payload(self):
        return {
            "rewritten_title": "融资前先看这几点",
            "rewritten_summary": "企业融资前，先理清需求、成本与风险。",
            "rewritten_content": "优化后的正文",
            "rewritten_html_content": "<section><p>优化后的正文</p></section>",
        }

    def test_article_not_found_returns_404(self):
        """文章不存在时应返回 404。"""
        conn = _FakeConnection(article_exists=False)
        with patch.object(article_service_module, "get_db", return_value=conn), \
             patch.object(article_service_module, "is_mysql", return_value=False):
            result, status_code = ArticleService.apply_ai_rewrite(999, self._valid_payload())

        self.assertEqual(status_code, 404)
        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "文章不存在")

    def test_empty_title_returns_400(self):
        """标题为空时应返回 400。"""
        payload = self._valid_payload()
        payload["rewritten_title"] = ""

        result, status_code = ArticleService.apply_ai_rewrite(1, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(result["msg"], "优化稿标题不能为空")

    def test_too_long_title_returns_400(self):
        """标题超过 40 字时应返回 400。"""
        payload = self._valid_payload()
        payload["rewritten_title"] = "这是一条超过四十个字的文章标题用于测试后端是否会拒绝过长标题避免写入异常内容请不要保存"

        result, status_code = ArticleService.apply_ai_rewrite(1, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(result["msg"], "优化稿标题不能超过 40 字")

    def test_unsafe_html_returns_400(self):
        """HTML 包含 script 等不兼容标签时应返回 400。"""
        payload = self._valid_payload()
        payload["rewritten_html_content"] = "<section><script>alert(1)</script></section>"

        result, status_code = ArticleService.apply_ai_rewrite(1, payload)

        self.assertEqual(status_code, 400)
        self.assertEqual(result["msg"], "优化稿包含不兼容标签，请重新生成")

    def test_valid_payload_updates_article(self):
        """正常 payload 应写回文章内容字段。"""
        conn = _FakeConnection(article_exists=True)
        with patch.object(article_service_module, "get_db", return_value=conn), \
             patch.object(article_service_module, "is_mysql", return_value=False):
            result, status_code = ArticleService.apply_ai_rewrite(1, self._valid_payload())

        self.assertEqual(status_code, 200)
        self.assertTrue(result["ok"])
        self.assertTrue(conn.committed)
        update_sql, update_params = conn.executed[1]
        self.assertIn("UPDATE articles", update_sql)
        self.assertEqual(update_params[-1], 1)

    def test_update_does_not_modify_status_fields(self):
        """写回 SQL 不应修改 status/review_status/publish_status。"""
        conn = _FakeConnection(article_exists=True)
        with patch.object(article_service_module, "get_db", return_value=conn), \
             patch.object(article_service_module, "is_mysql", return_value=False):
            ArticleService.apply_ai_rewrite(1, self._valid_payload())

        update_sql = conn.executed[1][0]
        self.assertNotIn("status=", update_sql)
        self.assertNotIn("review_status", update_sql)
        self.assertNotIn("publish_status", update_sql)


if __name__ == "__main__":
    unittest.main()
