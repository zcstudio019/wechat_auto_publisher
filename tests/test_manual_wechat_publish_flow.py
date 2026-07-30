import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database
from services.publish_service import PublishService
from services.publish_task_service import PublishTaskService
from services.review_service import ReviewService


class ManualWechatPublishFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="wechat_manual_publish_")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir, "articles.db")
        self.patchers = [
            patch("services.review_service.is_mysql", return_value=False),
            patch("services.publish_service.is_mysql", return_value=False),
            patch("services.publish_task_service.is_mysql", return_value=False),
        ]
        for item in self.patchers:
            item.start()
        self._create_schema()

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()
        database.DB_PATH = self.original_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_schema(self):
        conn = database.get_db()
        try:
            conn.executescript(
                """
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    status TEXT DEFAULT 'draft',
                    review_status TEXT DEFAULT 'pending_review',
                    publish_status TEXT DEFAULT 'not_ready',
                    draft_id TEXT,
                    wechat_media_id TEXT,
                    created_at DATETIME DEFAULT (datetime('now','localtime')),
                    updated_at DATETIME DEFAULT (datetime('now','localtime')),
                    published_at DATETIME
                );
                CREATE TABLE publish_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'wechat',
                    task_type TEXT NOT NULL DEFAULT 'wechat_draft',
                    status TEXT DEFAULT 'queued',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    payload_snapshot TEXT,
                    result_payload TEXT,
                    external_draft_id TEXT,
                    external_publish_id TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT (datetime('now','localtime')),
                    updated_at DATETIME DEFAULT (datetime('now','localtime')),
                    executed_at DATETIME
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_article(self, title="普通模板文章", tags="品牌宣传"):
        conn = database.get_db()
        try:
            cursor = conn.execute(
                """
                INSERT INTO articles (title, content, tags, status, review_status, publish_status)
                VALUES (?, '正文', ?, 'draft', 'pending_review', 'not_ready')
                """,
                (title, tags),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _article(self, article_id):
        conn = database.get_db()
        try:
            return dict(conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone())
        finally:
            conn.close()

    def test_approval_only_changes_review_status_and_creates_no_task(self):
        article_id = self._insert_article()

        result, status_code = ReviewService.approve_article(article_id)

        article = self._article(article_id)
        conn = database.get_db()
        try:
            task_count = conn.execute(
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=?", (article_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(status_code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(article["review_status"], "approved")
        self.assertEqual(article["publish_status"], "not_ready")
        self.assertEqual(article["status"], "draft")
        self.assertEqual(task_count, 0)

    def test_manual_push_creates_wechat_draft_without_publish_api(self):
        article_id = self._insert_article()
        ReviewService.approve_article(article_id)

        with patch(
            "services.publish_service.publish_single_article",
            return_value="wechat-media-001",
        ) as create_draft, patch(
            "wechat_api.client.submit_draft_for_review"
        ) as publish_api:
            result, status_code = PublishService.push_single_article(article_id)

        article = self._article(article_id)
        self.assertEqual(status_code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["wechat_media_id"], "wechat-media-001")
        self.assertEqual(article["publish_status"], "wechat_draft")
        self.assertEqual(article["wechat_media_id"], "wechat-media-001")
        self.assertEqual(article["draft_id"], "wechat-media-001")
        self.assertIsNone(article["published_at"])
        create_draft.assert_called_once()
        self.assertFalse(create_draft.call_args.kwargs["auto_submit"])
        publish_api.assert_not_called()

    def test_published_requires_two_explicit_human_confirmations(self):
        article_id = self._insert_article()
        ReviewService.approve_article(article_id)
        with patch("services.publish_service.publish_single_article", return_value="wechat-media-002"):
            PublishService.push_single_article(article_id)

        early_result, early_code = PublishService.confirm_published(article_id)
        self.assertEqual(early_code, 400)
        self.assertFalse(early_result["ok"])
        self.assertEqual(self._article(article_id)["publish_status"], "wechat_draft")

        waiting_result, waiting_code = PublishService.mark_waiting_publish(article_id)
        self.assertEqual(waiting_code, 200)
        self.assertTrue(waiting_result["ok"])
        self.assertEqual(self._article(article_id)["publish_status"], "waiting_publish")

        published_result, published_code = PublishService.confirm_published(article_id)
        article = self._article(article_id)
        self.assertEqual(published_code, 200)
        self.assertTrue(published_result["ok"])
        self.assertEqual(article["publish_status"], "published")
        self.assertIsNotNone(article["published_at"])

    def test_legacy_queued_task_only_creates_draft(self):
        article_id = self._insert_article(tags="文章增长中心")
        ReviewService.approve_article(article_id)
        task_id = PublishTaskService.create_task_for_article(article_id)

        with patch(
            "services.publish_task_service.publish_single_article",
            return_value="wechat-media-task",
        ), patch("wechat_api.client.submit_draft_for_review") as publish_api:
            result = PublishTaskService.execute_task(task_id)

        article = self._article(article_id)
        self.assertTrue(result["ok"])
        self.assertFalse(result["publish_submitted"])
        self.assertEqual(article["publish_status"], "wechat_draft")
        self.assertIsNone(article["published_at"])
        publish_api.assert_not_called()

    def test_other_template_article_is_unchanged_until_human_action(self):
        brand_id = self._insert_article(title="品牌宣传模板文章", tags="品牌宣传")
        growth_id = self._insert_article(title="增长中心文章", tags="industry_law")
        before_growth = self._article(growth_id)

        ReviewService.approve_article(brand_id)

        after_growth = self._article(growth_id)
        self.assertEqual(after_growth["title"], before_growth["title"])
        self.assertEqual(after_growth["review_status"], "pending_review")
        self.assertEqual(after_growth["publish_status"], "not_ready")


    def test_old_draft_sent_data_migrates_to_new_lifecycle(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                status TEXT,
                review_status TEXT,
                publish_status TEXT,
                draft_id TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO articles VALUES (1, 'draft_sent', 'approved', 'draft_sent', 'media-old')"
        )
        with patch("database.is_mysql", return_value=False):
            database._ensure_article_status_columns(conn)
            database._ensure_article_publish_lifecycle_columns(conn)

        article = dict(conn.execute("SELECT * FROM articles").fetchone())
        conn.close()
        self.assertEqual(article["review_status"], "approved")
        self.assertEqual(article["publish_status"], "wechat_draft")
        self.assertEqual(article["wechat_media_id"], "media-old")

    def test_very_old_database_preserves_published_state_when_columns_are_added(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE articles (id INTEGER PRIMARY KEY, status TEXT, draft_id TEXT)"
        )
        conn.execute("INSERT INTO articles VALUES (1, 'published', 'media-published')")
        with patch("database.is_mysql", return_value=False):
            database._ensure_article_status_columns(conn)
            database._ensure_article_publish_lifecycle_columns(conn)

        article = dict(conn.execute("SELECT * FROM articles").fetchone())
        conn.close()
        self.assertEqual(article["review_status"], "approved")
        self.assertEqual(article["publish_status"], "published")
        self.assertEqual(article["wechat_media_id"], "media-published")

    def test_scheduler_registers_no_automatic_approved_article_publish_job(self):
        from scheduler_app import build_scheduler

        scheduler = build_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}

        self.assertNotIn("daily_publish", job_ids)
        self.assertFalse(any(job_id.startswith("publish_") for job_id in job_ids))


if __name__ == "__main__":
    unittest.main()