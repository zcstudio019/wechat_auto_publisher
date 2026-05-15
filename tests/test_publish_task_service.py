import os
import json
import shutil
import unittest
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import database
from services.publish_task_service import (
    PublishTaskService,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_FAILED,
    TASK_STATUS_QUEUED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCESS,
    json_default,
)


class PublishTaskServiceTestCase(unittest.TestCase):
    """发布任务服务的最小回归测试。"""

    def setUp(self):
        """为每个用例创建独立临时数据库，避免影响真实数据。"""
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        self.temp_dir = os.path.join(data_dir, f"publish_task_service_test_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=False)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir, "test_articles.db")
        self.state_file_path = os.path.join(self.temp_dir, "system_state.json")
        self.events_file_path = os.path.join(self.temp_dir, "system_events.json")
        self.heartbeat_file_path = os.path.join(self.temp_dir, "worker_heartbeat.json")

        self.state_path_patcher = patch(
            "services.publish_task_service.SYSTEM_STATE_FILE_PATH",
            self.state_file_path,
        )
        self.events_path_patcher = patch(
            "services.publish_task_service.SYSTEM_EVENTS_FILE_PATH",
            self.events_file_path,
        )
        self.heartbeat_path_patcher = patch(
            "services.publish_task_service.WORKER_HEARTBEAT_FILE_PATH",
            self.heartbeat_file_path,
        )
        self.state_path_patcher.start()
        self.events_path_patcher.start()
        self.heartbeat_path_patcher.start()
        self._init_schema()

    def tearDown(self):
        """清理临时数据库并恢复原始配置。"""
        self.heartbeat_path_patcher.stop()
        self.events_path_patcher.stop()
        self.state_path_patcher.stop()
        database.DB_PATH = self.original_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _init_schema(self):
        """创建测试所需的最小 publish_tasks 表结构。"""
        conn = database.get_db()
        try:
            conn.execute(
                """
                CREATE TABLE publish_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    task_type TEXT NOT NULL,
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
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_task(
        self,
        article_id=1,
        status=TASK_STATUS_QUEUED,
        error_message="",
        created_at=None,
        updated_at=None,
        retry_count=0,
        max_retries=3,
    ):
        """插入一条发布任务测试数据。"""
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = created_at or now_text
        updated_at = updated_at or created_at

        conn = database.get_db()
        try:
            cursor = conn.execute(
                """
                INSERT INTO publish_tasks
                (article_id, channel, task_type, status, retry_count, max_retries, error_message, created_at, updated_at)
                VALUES (?, 'wechat', 'wechat_draft', ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    status,
                    retry_count,
                    max_retries,
                    error_message,
                    created_at,
                    updated_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _get_task_status(self, task_id):
        """读取指定任务的当前状态。"""
        conn = database.get_db()
        try:
            row = conn.execute("SELECT status FROM publish_tasks WHERE id=?", (task_id,)).fetchone()
            return row["status"] if row else None
        finally:
            conn.close()

    def test_task_status_meta_centralizes_label_badge_and_permissions(self):
        """任务状态映射应集中提供中文文案、badge 样式和操作权限。"""
        failed_meta = PublishTaskService.get_task_status_meta(TASK_STATUS_FAILED)
        cancelled_meta = PublishTaskService.get_task_status_meta(TASK_STATUS_CANCELLED)
        unknown_meta = PublishTaskService.get_task_status_meta("paused")

        self.assertEqual(failed_meta["label"], "失败")
        self.assertEqual(failed_meta["badge_class"], "bg-danger")
        self.assertTrue(failed_meta["can_retry"])
        self.assertEqual(cancelled_meta["label"], "已取消")
        self.assertFalse(cancelled_meta["can_cancel"])
        self.assertEqual(unknown_meta["label"], "paused")
        self.assertEqual(unknown_meta["badge_class"], "bg-light text-dark border")

    def test_json_default_serializes_mysql_datetime_values(self):
        """MySQL/PyMySQL 返回 datetime/date 时，发布任务快照应可安全 JSON 序列化。"""
        payload = {
            "created_at": datetime(2026, 5, 15, 9, 30, 5),
            "published_on": date(2026, 5, 15),
        }

        encoded = json.dumps(payload, ensure_ascii=False, default=json_default)

        self.assertIn("2026-05-15T09:30:05", encoded)
        self.assertIn("2026-05-15", encoded)

    def test_task_status_options_are_generated_from_status_mapping(self):
        """任务状态筛选项应由统一状态映射生成。"""
        options = PublishTaskService.get_task_status_options(include_all=True)

        self.assertEqual(options[0], {"value": "", "label": "全部"})
        self.assertIn({"value": TASK_STATUS_QUEUED, "label": "排队中"}, options)
        self.assertIn({"value": TASK_STATUS_CANCELLED, "label": "已取消"}, options)

    def _write_heartbeat(self, seconds_ago=0):
        """写入测试用 worker 心跳文件。"""
        last_run_at = datetime.now() - timedelta(seconds=seconds_ago)
        with open(self.heartbeat_file_path, "w", encoding="utf-8") as heartbeat_file:
            json.dump(
                {"last_run_at": last_run_at.strftime("%Y-%m-%d %H:%M:%S")},
                heartbeat_file,
                ensure_ascii=False,
            )

    def test_list_tasks_supports_status_reason_article_and_stale_filters(self):
        """列表查询应支持状态、失败原因、文章ID和疑似积压筛选。"""
        stale_time = (datetime.now() - timedelta(minutes=11)).strftime("%Y-%m-%d %H:%M:%S")
        fresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stale_task_id = self._insert_task(article_id=10, status=TASK_STATUS_QUEUED, created_at=stale_time)
        self._insert_task(article_id=10, status=TASK_STATUS_FAILED, error_message="token expired")
        self._insert_task(article_id=20, status=TASK_STATUS_FAILED, error_message="network error")
        self._insert_task(article_id=10, status=TASK_STATUS_QUEUED, created_at=fresh_time)

        failed_tasks = PublishTaskService.list_tasks(status=TASK_STATUS_FAILED)
        self.assertEqual(len(failed_tasks), 2)
        self.assertEqual(failed_tasks[0]["status_meta"]["label"], "失败")
        self.assertTrue(failed_tasks[0]["status_meta"]["can_retry"])

        reason_tasks = PublishTaskService.list_tasks(status=TASK_STATUS_FAILED, reason="token expired")
        self.assertEqual(len(reason_tasks), 1)
        self.assertEqual(reason_tasks[0]["article_id"], 10)

        article_tasks = PublishTaskService.list_tasks(article_id=10)
        self.assertEqual(len(article_tasks), 3)

        stale_tasks = PublishTaskService.list_tasks(stale_queued=True)
        self.assertEqual([task["id"] for task in stale_tasks], [stale_task_id])

    def test_failed_reason_top_groups_failed_errors(self):
        """失败原因统计应按错误文本聚合，并忽略空错误。"""
        self._insert_task(status=TASK_STATUS_FAILED, error_message="token expired")
        self._insert_task(status=TASK_STATUS_FAILED, error_message="token expired")
        self._insert_task(status=TASK_STATUS_FAILED, error_message="network error")
        self._insert_task(status=TASK_STATUS_FAILED, error_message="")
        self._insert_task(status=TASK_STATUS_SUCCESS, error_message="token expired")

        reasons = PublishTaskService.get_failed_reason_top(limit=3)

        self.assertEqual(reasons[0], {"reason": "token expired", "count": 2})
        self.assertEqual(reasons[1], {"reason": "network error", "count": 1})

    def test_retry_tasks_aggregates_results_and_continues_after_failure(self):
        """批量重试应逐个执行，单个失败不影响后续任务。"""
        task_ids = [101, 102, 103]

        def fake_retry_task(task_id):
            if task_id == 102:
                raise RuntimeError("模拟异常")
            return {"ok": task_id == 101}

        with patch.object(PublishTaskService, "retry_task", side_effect=fake_retry_task):
            result = PublishTaskService.retry_tasks(task_ids)

        self.assertEqual(result["processed_count"], 3)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failed_count"], 2)

    def test_recover_stuck_running_tasks_only_recovers_running_tasks(self):
        """恢复卡住任务时只允许 running 任务变回 queued。"""
        running_task_id = self._insert_task(status=TASK_STATUS_RUNNING)
        failed_task_id = self._insert_task(status=TASK_STATUS_FAILED)

        result = PublishTaskService.recover_stuck_running_tasks([running_task_id, failed_task_id])

        self.assertEqual(result["processed_count"], 2)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(self._get_task_status(running_task_id), TASK_STATUS_QUEUED)
        self.assertEqual(self._get_task_status(failed_task_id), TASK_STATUS_FAILED)

    def test_cancel_tasks_only_cancels_queued_tasks(self):
        """清空排队任务时只允许 queued 任务变为 cancelled。"""
        queued_task_id = self._insert_task(status=TASK_STATUS_QUEUED)
        running_task_id = self._insert_task(status=TASK_STATUS_RUNNING)

        result = PublishTaskService.cancel_tasks([queued_task_id, running_task_id])

        self.assertEqual(result["processed_count"], 2)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(self._get_task_status(queued_task_id), TASK_STATUS_CANCELLED)
        self.assertEqual(self._get_task_status(running_task_id), TASK_STATUS_RUNNING)

    def test_today_quality_summary_calculates_today_rates(self):
        """今日运行质量摘要应只统计今日 success 与 failed。"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        self._insert_task(status=TASK_STATUS_SUCCESS)
        self._insert_task(status=TASK_STATUS_SUCCESS)
        self._insert_task(status=TASK_STATUS_FAILED)
        self._insert_task(status=TASK_STATUS_FAILED, updated_at=yesterday)

        summary = PublishTaskService.get_today_quality_summary()

        self.assertEqual(summary["total_count"], 3)
        self.assertEqual(summary["success_count"], 2)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["success_rate"], 66.7)
        self.assertEqual(summary["failed_rate"], 33.3)

    def test_task_trend_24h_counts_success_failed_and_created_by_hour(self):
        """最近24小时趋势应按小时统计成功、失败和新建任务。"""
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_hour = datetime.now().strftime("%H:00")
        old_text = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

        self._insert_task(status=TASK_STATUS_SUCCESS, created_at=now_text, updated_at=now_text)
        self._insert_task(status=TASK_STATUS_FAILED, created_at=now_text, updated_at=now_text)
        self._insert_task(status=TASK_STATUS_QUEUED, created_at=now_text, updated_at=now_text)
        self._insert_task(status=TASK_STATUS_SUCCESS, created_at=old_text, updated_at=old_text)

        trend = PublishTaskService.get_task_trend_24h()
        current_bucket = next(item for item in trend if item["hour"] == current_hour)

        self.assertEqual(len(trend), 24)
        self.assertEqual(current_bucket["success_count"], 1)
        self.assertEqual(current_bucket["failed_count"], 1)
        self.assertEqual(current_bucket["created_count"], 3)

    def test_system_health_check_composes_existing_metrics(self):
        """系统自检应复用现有健康指标并生成整体状态。"""
        worker_health = {
            "last_run_at": "2026-04-21 10:00:00",
            "seconds_ago": 180,
            "is_healthy": False,
        }
        queue_health_summary = {
            "queued_count": 3,
            "running_count": 1,
            "failed_today_count": 2,
            "oldest_queued_created_at": "2026-04-21 09:40:00",
            "stale_queued_count": 1,
        }
        today_quality_summary = {
            "total_count": 10,
            "success_count": 8,
            "failed_count": 2,
            "success_rate": 80.0,
            "failed_rate": 20.0,
        }

        with patch.object(PublishTaskService, "get_worker_health", return_value=worker_health), \
            patch.object(PublishTaskService, "get_queue_health_summary", return_value=queue_health_summary), \
            patch.object(PublishTaskService, "get_stuck_running_tasks", return_value=[{"id": 1}]), \
            patch.object(PublishTaskService, "get_today_quality_summary", return_value=today_quality_summary), \
            patch.object(PublishTaskService, "get_today_failed_reason_top", return_value=[{"reason": "token expired", "count": 2}]), \
            patch.object(PublishTaskService, "get_failed_reason_top", return_value=[{"reason": "network error", "count": 3}]):
            health_check = PublishTaskService.get_system_health_check()

        self.assertEqual(health_check["overall_level"], "danger")
        self.assertEqual(health_check["worker_health"], worker_health)
        self.assertEqual(health_check["queue_health_summary"], queue_health_summary)
        self.assertEqual(health_check["stuck_running_count"], 1)
        self.assertEqual(len(health_check["check_items"]), 4)
        self.assertEqual(health_check["today_failed_reason_top"][0]["reason"], "token expired")

    def test_system_alerts_are_sorted_and_written_as_actionable_events(self):
        """系统告警应按优先级排序，并写入可操作事件。"""
        old_time = (datetime.now() - timedelta(minutes=11)).strftime("%Y-%m-%d %H:%M:%S")
        self._insert_task(status=TASK_STATUS_FAILED, error_message="token expired")
        self._insert_task(status=TASK_STATUS_QUEUED, created_at=old_time, updated_at=old_time)
        self._insert_task(status=TASK_STATUS_RUNNING, updated_at=old_time)

        alerts = PublishTaskService.get_system_alerts()
        titles = [alert["title"] for alert in alerts]

        self.assertEqual(titles[0], "后台执行器疑似异常")
        self.assertIn("今日失败率偏高", titles)
        self.assertIn("存在疑似卡住任务", titles)
        self.assertIn("存在疑似积压任务", titles)

        failed_alert = next(alert for alert in alerts if alert["title"] == "今日失败率偏高")
        self.assertEqual(failed_alert["action_url"], "/publish-tasks?status=failed")

        events = PublishTaskService.get_system_event_timeline(limit=10)
        failed_event = next(event for event in events if event["title"] == "今日失败率偏高")
        self.assertEqual(failed_event["type"], "alert")
        self.assertEqual(failed_event["action_url"], "/publish-tasks?status=failed")

    def test_system_recoveries_only_emit_on_state_transition(self):
        """恢复提示应只在旧异常变为新正常时产生，并写入事件。"""
        self._write_heartbeat(seconds_ago=10)
        with open(self.state_file_path, "w", encoding="utf-8") as state_file:
            json.dump(
                {
                    "worker_healthy": False,
                    "has_stale_queue": True,
                    "has_stuck_running": True,
                    "high_failed_rate": True,
                },
                state_file,
                ensure_ascii=False,
            )

        recoveries = PublishTaskService.get_system_recoveries()

        self.assertEqual(len(recoveries), 2)
        self.assertEqual(recoveries[0]["title"], "后台执行器刚刚恢复正常")
        self.assertEqual(recoveries[1]["title"], "积压任务已清空")
        self.assertEqual(recoveries[1]["action_url"], "/publish-tasks?status=queued")

        events = PublishTaskService.get_system_event_timeline(limit=10)
        recovery_events = [event for event in events if event["type"] == "recovery"]
        self.assertEqual(len(recovery_events), 4)

        # 第二次读取状态没有新的异常恢复变化，不应继续重复提示。
        self.assertEqual(PublishTaskService.get_system_recoveries(), [])

    def test_event_timeline_enriches_recovery_duration(self):
        """事件时间线应为有对应告警的恢复事件补充持续时长。"""
        events = [
            {
                "type": "recovery",
                "title": "Worker 刚刚恢复正常",
                "message": "后台轮询执行器已恢复心跳",
                "level": "success",
                "created_at": "2026-04-21 11:08:00",
            },
            {
                "type": "alert",
                "title": "Worker 疑似异常",
                "message": "最近超过 120 秒未轮询，请检查后台执行器",
                "level": "warning",
                "created_at": "2026-04-21 10:00:00",
            },
        ]

        enriched_events = PublishTaskService.enrich_system_events_with_duration(events)

        self.assertEqual(enriched_events[0]["duration_text"], "持续 1 小时 8 分钟")
        self.assertEqual(enriched_events[1].get("duration_text"), "")

    def test_event_timeline_enriches_event_group(self):
        """事件时间线应为事件补充分组标签。"""
        events = [
            {
                "type": "alert",
                "title": "Worker 疑似异常",
                "message": "最近超过 120 秒未轮询，请检查后台执行器",
                "level": "warning",
                "created_at": "2026-04-21 10:00:00",
            },
            {
                "type": "recovery",
                "title": "积压任务已清空",
                "message": "当前不存在超过 10 分钟仍 queued 的任务",
                "level": "success",
                "created_at": "2026-04-21 11:00:00",
            },
        ]

        enriched_events = PublishTaskService.enrich_system_events_with_duration(events)

        self.assertEqual(enriched_events[0]["event_group"], "后台执行器")
        self.assertEqual(enriched_events[1]["event_group"], "队列")

    def test_system_event_timeline_sorts_and_limits_events(self):
        """系统事件时间线应按时间倒序返回指定数量事件。"""
        events = [
            {
                "type": "alert",
                "title": "存在疑似积压任务",
                "message": "较早事件",
                "level": "warning",
                "created_at": "2026-04-21 10:00:00",
            },
            {
                "type": "recovery",
                "title": "积压任务已清空",
                "message": "较新事件",
                "level": "success",
                "created_at": "2026-04-21 10:05:00",
            },
            {
                "type": "alert",
                "title": "今日失败率偏高",
                "message": "最新事件",
                "level": "danger",
                "created_at": "2026-04-21 10:10:00",
            },
        ]
        PublishTaskService._write_system_events(events)

        timeline = PublishTaskService.get_system_event_timeline(limit=2)

        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["title"], "今日失败率偏高")
        self.assertEqual(timeline[1]["title"], "积压任务已清空")
        self.assertEqual(timeline[1]["duration_text"], "持续 5 分钟")

    def test_read_system_events_rebuilds_broken_json_file(self):
        """系统事件文件损坏时应自动备份并重建为空列表。"""
        with open(self.events_file_path, "w", encoding="utf-8") as events_file:
            events_file.write("{broken json")

        events = PublishTaskService._read_system_events()
        backup_files = [
            filename
            for filename in os.listdir(self.temp_dir)
            if filename.startswith("system_events.json.bad.")
        ]

        self.assertEqual(events, [])
        self.assertTrue(backup_files)
        with open(self.events_file_path, "r", encoding="utf-8") as events_file:
            self.assertEqual(json.load(events_file), [])

    def test_append_system_event_skips_same_title_same_type_duplicate(self):
        """系统事件追加应跳过同标题同类型的重复事件。"""
        event = {
            "type": "alert",
            "title": "Worker 疑似异常",
            "message": "第一次告警",
            "level": "warning",
        }

        PublishTaskService.append_system_event(event)
        PublishTaskService.append_system_event(
            {
                "type": "alert",
                "title": "Worker 疑似异常",
                "message": "重复告警",
                "level": "warning",
            }
        )

        events = PublishTaskService._read_system_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"], "第一次告警")

    def test_append_system_event_allows_alert_after_recovery_transition(self):
        """系统事件恢复后再次异常时应允许写入新的告警事件。"""
        PublishTaskService._write_system_events(
            [
                {
                    "type": "recovery",
                    "title": "Worker 刚刚恢复正常",
                    "message": "后台轮询执行器已恢复心跳",
                    "level": "success",
                    "created_at": "2026-04-21 10:05:00",
                },
                {
                    "type": "alert",
                    "title": "Worker 疑似异常",
                    "message": "旧告警",
                    "level": "warning",
                    "created_at": "2026-04-21 10:00:00",
                },
            ]
        )

        PublishTaskService.append_system_event(
            {
                "type": "alert",
                "title": "Worker 疑似异常",
                "message": "恢复后再次告警",
                "level": "warning",
            }
        )

        events = PublishTaskService._read_system_events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["title"], "Worker 疑似异常")
        self.assertEqual(events[0]["message"], "恢复后再次告警")

    def test_write_system_events_keeps_latest_configured_count(self):
        """系统事件写入应只保留配置的最近事件数量。"""
        events = []
        for index in range(25):
            events.append(
                {
                    "type": "alert",
                    "title": f"事件{index}",
                    "message": "测试事件",
                    "level": "warning",
                    "created_at": f"2026-04-21 10:{index:02d}:00",
                }
            )

        PublishTaskService._write_system_events(events)
        saved_events = PublishTaskService._read_system_events()

        self.assertEqual(len(saved_events), 20)
        self.assertEqual(saved_events[0]["title"], "事件24")
        self.assertEqual(saved_events[-1]["title"], "事件5")


if __name__ == "__main__":
    unittest.main()
