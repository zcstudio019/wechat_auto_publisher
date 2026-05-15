import unittest

from web_ui.app import _delete_article_related_rows, _is_missing_table_error


class _FakeCursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeConnection:
    def __init__(self, missing_tables=None):
        self.calls = []
        self.missing_tables = set(missing_tables or [])

    def execute(self, sql, params):
        table = sql.split("DELETE FROM ", 1)[1].split(" ", 1)[0]
        self.calls.append((table, sql, params))
        if table in self.missing_tables:
            raise Exception("no such table: " + table)
        return _FakeCursor(len(self.calls))


class ArticleDeleteTestCase(unittest.TestCase):
    def test_missing_table_error_detection_supports_sqlite_and_mysql(self):
        self.assertTrue(_is_missing_table_error(Exception("no such table: review_actions")))
        self.assertTrue(_is_missing_table_error(Exception(1146, "Table 'db.channel_drafts' doesn't exist")))
        self.assertFalse(_is_missing_table_error(Exception("foreign key constraint fails")))

    def test_delete_related_rows_uses_safe_order_and_continues_on_missing_table(self):
        conn = _FakeConnection(missing_tables={"review_actions"})

        counts = _delete_article_related_rows(conn, article_id=9, placeholder="?")

        self.assertEqual(
            [call[0] for call in conn.calls],
            [
                "ai_operation_logs",
                "cover_generation_tasks",
                "publish_tasks",
                "review_actions",
                "channel_drafts",
            ],
        )
        self.assertEqual(counts["review_actions"], "missing")
        self.assertEqual(conn.calls[0][2], (9,))
        self.assertIn("article_id=?", conn.calls[0][1])


if __name__ == "__main__":
    unittest.main()
