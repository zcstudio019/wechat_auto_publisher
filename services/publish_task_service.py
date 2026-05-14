"""发布任务服务。"""

import json
import os
from datetime import datetime, timedelta

from database import get_db, is_mysql
from domain.article_status import STATUS_DRAFT_SENT, split_legacy_status
from wechat_api.publisher import publish_single_article

# 统一定义发布任务状态，便于后续异步化平滑接入。
TASK_STATUS_QUEUED = "queued"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELLED = "cancelled"

# 统一维护发布任务状态的展示文案、样式与轻量操作权限，避免模板散落重复判断。
TASK_STATUS_META = {
    TASK_STATUS_QUEUED: {
        "label": "排队中",
        "badge_class": "bg-secondary",
        "can_retry": False,
        "can_cancel": True,
        "can_recover": False,
    },
    TASK_STATUS_RUNNING: {
        "label": "执行中",
        "badge_class": "bg-warning text-dark",
        "can_retry": False,
        "can_cancel": False,
        "can_recover": True,
    },
    TASK_STATUS_SUCCESS: {
        "label": "成功",
        "badge_class": "bg-success",
        "can_retry": False,
        "can_cancel": False,
        "can_recover": False,
    },
    TASK_STATUS_FAILED: {
        "label": "失败",
        "badge_class": "bg-danger",
        "can_retry": True,
        "can_cancel": False,
        "can_recover": False,
    },
    TASK_STATUS_CANCELLED: {
        "label": "已取消",
        "badge_class": "bg-light text-dark border",
        "can_retry": False,
        "can_cancel": False,
        "can_recover": False,
    },
}

# 统一定义当前阶段使用的发布渠道与任务类型。
TASK_CHANNEL_WECHAT = "wechat"
TASK_TYPE_WECHAT_DRAFT = "wechat_draft"

# 统一定义 worker 心跳文件路径，便于服务层读取最近轮询状态。
WORKER_HEARTBEAT_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "worker_heartbeat.json",
)

# 统一定义系统状态文件路径，便于识别异常恢复事件。
SYSTEM_STATE_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "system_state.json",
)

# 统一定义系统事件文件路径，便于展示最近告警与恢复轨迹。
SYSTEM_EVENTS_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "system_events.json",
)

# 系统事件最多保留条数，后续如需调整只改这一处。
SYSTEM_EVENTS_MAX_KEEP = int(os.getenv("SYSTEM_EVENTS_MAX_KEEP", "20"))


class PublishTaskService:
    """封装发布任务的创建、执行与结果回写。"""

    @staticmethod
    def _fetchone(conn, mysql_sql: str, sqlite_sql: str, params=()):
        """执行单行查询，并显式区分 MySQL 与 SQLite 语法。"""
        if is_mysql():
            return conn.execute(mysql_sql, params).fetchone()
        return conn.execute(sqlite_sql, params).fetchone()

    @staticmethod
    def _fetchall(conn, mysql_sql: str, sqlite_sql: str, params=()):
        """执行多行查询，并显式区分 MySQL 与 SQLite 语法。"""
        if is_mysql():
            return conn.execute(mysql_sql, params).fetchall()
        return conn.execute(sqlite_sql, params).fetchall()

    @staticmethod
    def _execute(conn, mysql_sql: str, sqlite_sql: str, params=()):
        """执行写操作 SQL，并显式区分 MySQL 与 SQLite 语法。"""
        if is_mysql():
            return conn.execute(mysql_sql, params)
        return conn.execute(sqlite_sql, params)

    @staticmethod
    def get_task_status_meta(status: str) -> dict:
        """获取单个任务状态的统一展示配置。"""
        safe_status = (status or "").strip()
        # 未知状态也返回稳定结构，避免模板遇到新状态时报错。
        return dict(
            TASK_STATUS_META.get(
                safe_status,
                {
                    "label": safe_status or "-",
                    "badge_class": "bg-light text-dark border",
                    "can_retry": False,
                    "can_cancel": False,
                    "can_recover": False,
                },
            )
        )

    @staticmethod
    def get_task_status_map() -> dict:
        """获取全部任务状态展示映射。"""
        # 返回副本，避免调用方误改全局映射。
        return {
            status: PublishTaskService.get_task_status_meta(status)
            for status in TASK_STATUS_META
        }

    @staticmethod
    def get_task_status_options(include_all: bool = False) -> list[dict]:
        """获取任务状态筛选选项。"""
        options = []
        if include_all:
            options.append({"value": "", "label": "全部"})

        # 筛选项集中从映射生成，后续新增状态时不再需要同步修改模板。
        for status in TASK_STATUS_META:
            options.append(
                {
                    "value": status,
                    "label": TASK_STATUS_META[status]["label"],
                }
            )
        return options

    @staticmethod
    def _read_system_state() -> dict | None:
        """读取上一次记录的系统状态。"""
        # 状态文件不存在时返回空，交由上层按首次初始化处理。
        if not os.path.exists(SYSTEM_STATE_FILE_PATH):
            return None

        try:
            with open(SYSTEM_STATE_FILE_PATH, "r", encoding="utf-8") as state_file:
                state_data = json.load(state_file)
            return dict(state_data) if isinstance(state_data, dict) else None
        except Exception:
            # 状态文件损坏时按不存在处理，避免影响页面主流程。
            return None

    @staticmethod
    def _write_system_state(state: dict):
        """写入当前系统状态快照。"""
        # 每次页面读取后都回写最新状态，便于下次识别是否发生恢复事件。
        os.makedirs(os.path.dirname(SYSTEM_STATE_FILE_PATH), exist_ok=True)
        with open(SYSTEM_STATE_FILE_PATH, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, ensure_ascii=False)

    @staticmethod
    def _read_system_events() -> list[dict]:
        """读取系统事件列表。"""
        # 事件文件不存在时返回空列表，避免影响页面主流程。
        if not os.path.exists(SYSTEM_EVENTS_FILE_PATH):
            return []

        try:
            with open(SYSTEM_EVENTS_FILE_PATH, "r", encoding="utf-8") as events_file:
                events_data = json.load(events_file)
            return events_data if isinstance(events_data, list) else []
        except Exception:
            # 事件文件损坏时自动备份并重建为空列表，避免长期影响监控体验。
            PublishTaskService._backup_broken_system_events_file()
            PublishTaskService._write_system_events([])
            return []

    @staticmethod
    def _write_system_events(events: list[dict]):
        """写入系统事件列表。"""
        # 事件文件只保存最近少量记录，保持文件轻量可控。
        os.makedirs(os.path.dirname(SYSTEM_EVENTS_FILE_PATH), exist_ok=True)
        events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        with open(SYSTEM_EVENTS_FILE_PATH, "w", encoding="utf-8") as events_file:
            json.dump(events[:SYSTEM_EVENTS_MAX_KEEP], events_file, ensure_ascii=False, indent=2)

    @staticmethod
    def _backup_broken_system_events_file():
        """备份损坏的系统事件文件。"""
        if not os.path.exists(SYSTEM_EVENTS_FILE_PATH):
            return

        try:
            broken_file_path = (
                f"{SYSTEM_EVENTS_FILE_PATH}.bad."
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            os.replace(SYSTEM_EVENTS_FILE_PATH, broken_file_path)
        except Exception:
            # 备份失败时不影响页面主流程，后续写入会尝试重建事件文件。
            pass

    @staticmethod
    def _should_skip_duplicate_system_event(events: list[dict], event: dict) -> bool:
        """判断是否应跳过重复系统事件。"""
        event_type = event.get("type", "")
        event_title = event.get("title", "")
        event_group = PublishTaskService._infer_event_group(event_title)

        # 按事件分组查看最近一次状态，避免同类告警刷屏，同时允许恢复后再次告警。
        for existing_event in events:
            existing_group = PublishTaskService._infer_event_group(existing_event.get("title", ""))
            if existing_group == event_group:
                return existing_event.get("type") == event_type

        return False

    @staticmethod
    def append_system_event(event: dict):
        """追加系统事件，并避免同类事件在自动刷新中重复刷屏。"""
        events = PublishTaskService._read_system_events()

        # 如果同一分组最近一次事件类型相同，则说明状态没有变化，不重复记录。
        if PublishTaskService._should_skip_duplicate_system_event(events, event):
            return

        # 补充事件发生时间，并交给写入方法按配置控制最多保留条数。
        event["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        events.append(event)
        PublishTaskService._write_system_events(events)

    @staticmethod
    def get_task(task_id: int):
        """根据任务ID获取任务详情。"""
        conn = get_db()
        try:
            # 返回原始任务记录，便于接口层按需输出。
            task = PublishTaskService._fetchone(
                conn,
                "SELECT * FROM publish_tasks WHERE id=%s",
                "SELECT * FROM publish_tasks WHERE id=?",
                (task_id,),
            )
            return dict(task) if task else None
        finally:
            conn.close()

    @staticmethod
    def get_stuck_running_tasks(limit: int = 100) -> list[dict]:
        """获取疑似卡住的 running 任务列表。"""
        conn = get_db()
        try:
            # 对查询数量做轻量保护，避免页面一次展示过多卡住任务。
            safe_limit = max(1, min(limit or 100, 200))

            rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT *
                FROM publish_tasks
                WHERE status=%s AND updated_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)
                ORDER BY id DESC
                LIMIT %s
                """,
                """
                SELECT *
                FROM publish_tasks
                WHERE status=? AND updated_at <= datetime('now','localtime','-10 minutes')
                ORDER BY id DESC
                LIMIT ?
                """,
                (TASK_STATUS_RUNNING, safe_limit),
            )

            stuck_tasks = []
            for row in rows:
                task = dict(row)

                # 为页面补充一个轻量分钟差展示，便于运营快速判断卡住时长。
                minutes_ago = 10
                updated_at = (task.get("updated_at") or "").strip()
                if updated_at:
                    try:
                        updated_at_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
                        minutes_ago = max(10, int((datetime.now() - updated_at_dt).total_seconds() // 60))
                    except Exception:
                        minutes_ago = 10

                task["minutes_ago"] = minutes_ago
                stuck_tasks.append(task)

            return stuck_tasks
        finally:
            conn.close()

    @staticmethod
    def recover_stuck_running_tasks(task_ids: list[int]) -> dict:
        """批量恢复疑似卡住的 running 任务为 queued。"""
        # 空列表时直接安全返回，避免无意义处理。
        if not task_ids:
            return {
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
            }

        processed_count = 0
        success_count = 0
        failed_count = 0

        conn = get_db()
        try:
            for task_id in task_ids:
                processed_count += 1
                try:
                    # 逐个读取任务状态，仅允许 running 任务被恢复。
                    task = PublishTaskService._fetchone(
                        conn,
                        "SELECT status FROM publish_tasks WHERE id=%s",
                        "SELECT status FROM publish_tasks WHERE id=?",
                        (task_id,),
                    )

                    if not task or task["status"] != TASK_STATUS_RUNNING:
                        failed_count += 1
                        continue

                    # 恢复卡住任务时仅更新任务状态，不回写文章状态。
                    cursor = PublishTaskService._execute(
                        conn,
                        """
                        UPDATE publish_tasks
                        SET status=%s, updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s AND status=%s
                        """,
                        """
                        UPDATE publish_tasks
                        SET status=?, updated_at=datetime('now','localtime')
                        WHERE id=? AND status=?
                        """,
                        (TASK_STATUS_QUEUED, task_id, TASK_STATUS_RUNNING),
                    )
                    if cursor.rowcount == 1:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    # 单个任务失败不影响其他任务继续处理。
                    failed_count += 1

            conn.commit()
        finally:
            conn.close()

        return {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
        }

    @staticmethod
    def retry_tasks(task_ids: list[int]) -> dict:
        """批量重试任务，单个任务失败不影响其他任务继续执行。"""
        # 空列表时直接安全返回，避免无意义处理。
        if not task_ids:
            return {
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
            }

        processed_count = 0
        success_count = 0
        failed_count = 0

        for task_id in task_ids:
            processed_count += 1
            try:
                # 逐个复用现有单任务重试逻辑，保持行为一致。
                result = PublishTaskService.retry_task(task_id)
                if result.get("ok"):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception:
                # 单个任务异常时仅计入失败，不中断后续任务处理。
                failed_count += 1

        return {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
        }

    @staticmethod
    def cancel_tasks(task_ids: list[int]) -> dict:
        """批量取消任务，仅允许取消排队中的任务。"""
        # 空列表时直接安全返回，避免无意义处理。
        if not task_ids:
            return {
                "processed_count": 0,
                "success_count": 0,
                "failed_count": 0,
            }

        processed_count = 0
        success_count = 0
        failed_count = 0

        conn = get_db()
        try:
            for task_id in task_ids:
                processed_count += 1
                try:
                    # 逐个读取任务状态，仅允许 queued 任务被取消。
                    task = PublishTaskService._fetchone(
                        conn,
                        "SELECT status FROM publish_tasks WHERE id=%s",
                        "SELECT status FROM publish_tasks WHERE id=?",
                        (task_id,),
                    )

                    if not task or task["status"] != TASK_STATUS_QUEUED:
                        failed_count += 1
                        continue

                    # 取消排队任务时仅更新任务状态，不回写文章状态。
                    cursor = PublishTaskService._execute(
                        conn,
                        """
                        UPDATE publish_tasks
                        SET status=%s, updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s AND status=%s
                        """,
                        """
                        UPDATE publish_tasks
                        SET status=?, updated_at=datetime('now','localtime')
                        WHERE id=? AND status=?
                        """,
                        (TASK_STATUS_CANCELLED, task_id, TASK_STATUS_QUEUED),
                    )
                    if cursor.rowcount == 1:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    # 单个任务失败不影响其他任务继续处理。
                    failed_count += 1

            conn.commit()
        finally:
            conn.close()

        return {
            "processed_count": processed_count,
            "success_count": success_count,
            "failed_count": failed_count,
        }

    @staticmethod
    def list_tasks(
        status: str | None = None,
        reason: str | None = None,
        article_id: int | None = None,
        stale_queued: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        """按状态倒序查询发布任务列表。"""
        conn = get_db()
        try:
            # 对查询数量做轻量保护，避免列表页一次读取过多任务。
            safe_limit = max(1, min(limit or 100, 200))

            # 疑似积压筛选优先级最高，仅支持最小必要组合：积压任务与文章任务积压。
            if stale_queued and article_id is not None:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=%s AND status=%s AND created_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=? AND status=? AND created_at <= datetime('now','localtime','-10 minutes')
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (article_id, TASK_STATUS_QUEUED, safe_limit),
                )
            elif stale_queued:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=%s AND created_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=? AND created_at <= datetime('now','localtime','-10 minutes')
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (TASK_STATUS_QUEUED, safe_limit),
                )

            # 同时支持按文章、状态和失败原因精确筛选，默认按任务ID倒序展示最近任务。
            elif article_id is not None and status and reason:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=%s AND status=%s AND error_message=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=? AND status=? AND error_message=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (article_id, status, reason, safe_limit),
                )
            elif article_id is not None and status:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=%s AND status=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=? AND status=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (article_id, status, safe_limit),
                )
            elif article_id is not None and reason:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=%s AND error_message=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=? AND error_message=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (article_id, reason, safe_limit),
                )
            elif article_id is not None:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE article_id=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (article_id, safe_limit),
                )
            elif status and reason:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=%s AND error_message=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=? AND error_message=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (status, reason, safe_limit),
                )
            elif status:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE status=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (status, safe_limit),
                )
            elif reason:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE error_message=%s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    WHERE error_message=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (reason, safe_limit),
                )
            else:
                rows = PublishTaskService._fetchall(
                    conn,
                    """
                    SELECT *
                    FROM publish_tasks
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    """
                    SELECT *
                    FROM publish_tasks
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )

            # 路由层直接使用字典列表渲染，并附带统一状态展示配置，保持模板简单稳定。
            tasks = []
            for row in rows:
                task = dict(row)
                task["status_meta"] = PublishTaskService.get_task_status_meta(task.get("status", ""))
                tasks.append(task)
            return tasks
        finally:
            conn.close()

    @staticmethod
    def get_task_stats() -> dict:
        """获取发布任务列表页所需的轻量统计数据。"""
        conn = get_db()
        try:
            # 分别统计排队中、失败中以及今日成功任务数量，保持查询语义清晰直观。
            queued_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE status=?",
                (TASK_STATUS_QUEUED,),
            )[0]
            failed_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE status=?",
                (TASK_STATUS_FAILED,),
            )[0]
            success_today_count = PublishTaskService._fetchone(
                conn,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=%s AND DATE(updated_at)=CURDATE()
                """,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=? AND DATE(updated_at)=DATE('now','localtime')
                """,
                (TASK_STATUS_SUCCESS,),
            )[0]

            # 统一返回简单字典，便于路由层直接透传给模板渲染。
            return {
                "queued_count": queued_count,
                "failed_count": failed_count,
                "success_today_count": success_today_count,
            }
        finally:
            conn.close()

    @staticmethod
    def get_task_trend_24h() -> list[dict]:
        """获取最近24小时任务趋势数据。"""
        conn = get_db()
        try:
            # 以当前整点为结束时间，向前生成 24 个小时桶，保持展示稳定直观。
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            start_time = now - timedelta(hours=23)
            start_time_text = start_time.strftime("%Y-%m-%d %H:%M:%S")
            buckets = {}

            for offset in range(24):
                current_hour = start_time + timedelta(hours=offset)
                bucket_key = current_hour.strftime("%Y-%m-%d %H:00:00")
                buckets[bucket_key] = {
                    "hour": current_hour.strftime("%H:00"),
                    "success_count": 0,
                    "failed_count": 0,
                    "created_count": 0,
                }

            # 成功任务按 updated_at 小时聚合，仅统计最近 24 小时范围内的数据。
            success_rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT DATE_FORMAT(updated_at, '%%Y-%%m-%%d %%H:00:00') AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=%s AND updated_at >= %s
                GROUP BY hour_key
                """,
                """
                SELECT strftime('%Y-%m-%d %H:00:00', updated_at) AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=? AND updated_at >= ?
                GROUP BY hour_key
                """,
                (TASK_STATUS_SUCCESS, start_time_text),
            )

            # 失败任务按 updated_at 小时聚合，仅统计最近 24 小时范围内的数据。
            failed_rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT DATE_FORMAT(updated_at, '%%Y-%%m-%%d %%H:00:00') AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=%s AND updated_at >= %s
                GROUP BY hour_key
                """,
                """
                SELECT strftime('%Y-%m-%d %H:00:00', updated_at) AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=? AND updated_at >= ?
                GROUP BY hour_key
                """,
                (TASK_STATUS_FAILED, start_time_text),
            )

            # 新建任务按 created_at 小时聚合，仅统计最近 24 小时范围内的数据。
            created_rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:00:00') AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE created_at >= %s
                GROUP BY hour_key
                """,
                """
                SELECT strftime('%Y-%m-%d %H:00:00', created_at) AS hour_key, COUNT(*) AS count
                FROM publish_tasks
                WHERE created_at >= ?
                GROUP BY hour_key
                """,
                (start_time_text,),
            )

            for row in success_rows:
                if row["hour_key"] in buckets:
                    buckets[row["hour_key"]]["success_count"] = row["count"]

            for row in failed_rows:
                if row["hour_key"] in buckets:
                    buckets[row["hour_key"]]["failed_count"] = row["count"]

            for row in created_rows:
                if row["hour_key"] in buckets:
                    buckets[row["hour_key"]]["created_count"] = row["count"]

            return list(buckets.values())
        finally:
            conn.close()

    @staticmethod
    def get_today_quality_summary() -> dict:
        """获取今日运行质量摘要。"""
        conn = get_db()
        try:
            # 今日成功任务仅按 updated_at 统计，口径与页面运行质量保持一致。
            success_count = PublishTaskService._fetchone(
                conn,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=%s AND DATE(updated_at)=CURDATE()
                """,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=? AND DATE(updated_at)=DATE('now','localtime')
                """,
                (TASK_STATUS_SUCCESS,),
            )[0]

            # 今日失败任务仅按 updated_at 统计，口径与成功任务一致。
            failed_count = PublishTaskService._fetchone(
                conn,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=%s AND DATE(updated_at)=CURDATE()
                """,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=? AND DATE(updated_at)=DATE('now','localtime')
                """,
                (TASK_STATUS_FAILED,),
            )[0]

            total_count = (success_count or 0) + (failed_count or 0)

            # 当天没有成功或失败任务时返回 0，避免出现除零问题。
            success_rate = round((success_count / total_count) * 100, 1) if total_count else 0.0
            failed_rate = round((failed_count / total_count) * 100, 1) if total_count else 0.0

            return {
                "total_count": total_count,
                "success_count": success_count or 0,
                "failed_count": failed_count or 0,
                "success_rate": success_rate,
                "failed_rate": failed_rate,
            }
        finally:
            conn.close()

    @staticmethod
    def get_today_failed_reason_top(limit: int = 5) -> list[dict]:
        """获取今日失败原因 TOP 列表。"""
        conn = get_db()
        try:
            # 对返回数量做轻量保护，避免页面一次展示过多失败原因。
            safe_limit = max(1, min(limit or 5, 10))

            # 仅统计今日失败任务，并按原始错误文本直接聚合，保持实现简单稳定。
            rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT error_message AS reason, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=%s AND DATE(updated_at)=CURDATE()
                  AND error_message IS NOT NULL AND TRIM(error_message) != ''
                GROUP BY error_message
                ORDER BY count DESC, MAX(id) DESC
                LIMIT %s
                """,
                """
                SELECT error_message AS reason, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=? AND DATE(updated_at)=DATE('now','localtime')
                  AND error_message IS NOT NULL AND TRIM(error_message) != ''
                GROUP BY error_message
                ORDER BY count DESC, MAX(id) DESC
                LIMIT ?
                """,
                (TASK_STATUS_FAILED, safe_limit),
            )

            return [
                {
                    "reason": row["reason"],
                    "count": row["count"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_system_alerts() -> list[dict]:
        """获取发布任务系统的自动告警列表。"""
        alerts = []

        # 复用现有只读统计方法，集中生成页面顶部告警提示。
        today_quality_summary = PublishTaskService.get_today_quality_summary()
        worker_health = PublishTaskService.get_worker_health()
        queue_health_summary = PublishTaskService.get_queue_health_summary()
        stuck_running_tasks = PublishTaskService.get_stuck_running_tasks(limit=20)

        # 今日失败率超过阈值时提示运营优先检查失败原因。
        if (today_quality_summary.get("failed_rate") or 0) > 10:
            alerts.append(
                {
                    "level": "danger",
                    "priority": 90,
                    "title": "今日失败率偏高",
                    "message": f"当前失败率为 {today_quality_summary.get('failed_rate', 0)}%，请优先检查失败原因前5",
                    "action_text": "查看失败任务",
                    "action_url": "/publish-tasks?status=failed",
                }
            )

        # 后台执行器心跳异常时提醒检查后台轮询执行器。
        if not worker_health.get("is_healthy"):
            alerts.append(
                {
                    "level": "warning",
                    "priority": 100,
                    "title": "后台执行器疑似异常",
                    "message": "最近超过 120 秒未轮询，请检查后台执行器",
                    "action_text": "",
                    "action_url": "",
                }
            )

        # 存在积压任务时提醒优先排查队列堵塞情况。
        if (queue_health_summary.get("stale_queued_count") or 0) > 0:
            alerts.append(
                {
                    "level": "warning",
                    "priority": 70,
                    "title": "存在疑似积压任务",
                    "message": f"当前有 {queue_health_summary.get('stale_queued_count', 0)} 个任务超过 10 分钟仍处于排队中",
                    "action_text": "查看积压任务",
                    "action_url": "/publish-tasks?stale_queued=1",
                }
            )

        # 存在卡住任务时提醒运营尽快恢复异常执行中状态。
        if len(stuck_running_tasks) > 0:
            alerts.append(
                {
                    "level": "warning",
                    "priority": 80,
                    "title": "存在疑似卡住任务",
                    "message": f"当前识别到 {len(stuck_running_tasks)} 个执行中任务超过 10 分钟未更新，可考虑一键恢复",
                    "action_text": "查看卡住任务",
                    "action_url": "/publish-tasks?status=running",
                }
            )

        # 按优先级倒序展示告警，高优先级问题始终排在最上方。
        alerts.sort(key=lambda item: item.get("priority", 0), reverse=True)

        for alert in alerts:
            # 告警生成时写入轻量事件，便于页面展示系统状态变化轨迹。
            PublishTaskService.append_system_event(
                {
                    "type": "alert",
                    "title": alert.get("title", ""),
                    "message": alert.get("message", ""),
                    "level": alert.get("level", "warning"),
                    "action_text": alert.get("action_text", ""),
                    "action_url": alert.get("action_url", ""),
                }
            )

        return alerts

    @staticmethod
    def get_system_recoveries() -> list[dict]:
        """获取发布任务系统的恢复提示列表。"""
        recoveries = []
        previous_state = PublishTaskService._read_system_state()
        current_state = PublishTaskService.get_current_system_state()

        # 首次运行仅初始化状态文件，不生成恢复提示，避免误报“刚刚恢复”。
        if previous_state is None:
            PublishTaskService._write_system_state(current_state)
            return recoveries

        # 后台执行器从异常恢复为正常时给出恢复提示。
        if previous_state.get("worker_healthy") is False and current_state.get("worker_healthy") is True:
            recoveries.append(
                {
                    "level": "success",
                    "title": "后台执行器刚刚恢复正常",
                    "message": "后台轮询执行器已恢复心跳",
                    "action_text": "",
                    "action_url": "",
                }
            )

        # 积压任务从存在变为清空时给出恢复提示。
        if previous_state.get("has_stale_queue") is True and current_state.get("has_stale_queue") is False:
            recoveries.append(
                {
                    "level": "success",
                    "title": "积压任务已清空",
                    "message": "当前不存在超过 10 分钟仍处于排队中的任务",
                    "action_text": "查看队列状态",
                    "action_url": "/publish-tasks?status=queued",
                }
            )

        # 卡住任务从存在变为清空时给出恢复提示。
        if previous_state.get("has_stuck_running") is True and current_state.get("has_stuck_running") is False:
            recoveries.append(
                {
                    "level": "success",
                    "title": "卡住任务已恢复",
                    "message": "当前不存在超过 10 分钟未更新的执行中任务",
                    "action_text": "查看运行任务",
                    "action_url": "/publish-tasks?status=running",
                }
            )

        # 今日失败率从超阈值恢复到正常时给出恢复提示。
        if previous_state.get("high_failed_rate") is True and current_state.get("high_failed_rate") is False:
            recoveries.append(
                {
                    "level": "success",
                    "title": "今日失败率已恢复正常",
                    "message": "当前失败率已回落到预警阈值以内",
                    "action_text": "查看今日失败",
                    "action_url": "/publish-tasks?status=failed",
                }
            )

        # 每次执行后都写回当前状态，为下次恢复对比提供基准。
        PublishTaskService._write_system_state(current_state)

        for recovery in recoveries:
            # 恢复提示生成时写入轻量事件，便于运营看到问题恢复时间。
            PublishTaskService.append_system_event(
                {
                    "type": "recovery",
                    "title": recovery.get("title", ""),
                    "message": recovery.get("message", ""),
                    "level": recovery.get("level", "success"),
                    "action_text": recovery.get("action_text", ""),
                    "action_url": recovery.get("action_url", ""),
                }
            )

        return recoveries[:2]

    @staticmethod
    def get_current_system_state() -> dict:
        """获取当前系统状态快照。"""
        # 复用现有只读方法，统一生成可持久化的轻量状态。
        worker_health = PublishTaskService.get_worker_health()
        queue_health_summary = PublishTaskService.get_queue_health_summary()
        stuck_running_tasks = PublishTaskService.get_stuck_running_tasks(limit=20)
        today_quality_summary = PublishTaskService.get_today_quality_summary()

        return {
            "worker_healthy": bool(worker_health.get("is_healthy")),
            "has_stale_queue": (queue_health_summary.get("stale_queued_count") or 0) > 0,
            "has_stuck_running": len(stuck_running_tasks) > 0,
            "high_failed_rate": (today_quality_summary.get("failed_rate") or 0) > 10,
        }

    @staticmethod
    def get_system_health_check() -> dict:
        """获取系统自检页所需的只读健康检查结果。"""
        # 自检页只复用现有轻量统计，不触发任务执行、不修改任务状态。
        worker_health = PublishTaskService.get_worker_health()
        queue_health_summary = PublishTaskService.get_queue_health_summary()
        stuck_running_tasks = PublishTaskService.get_stuck_running_tasks(limit=20)
        today_quality_summary = PublishTaskService.get_today_quality_summary()
        today_failed_reason_top = PublishTaskService.get_today_failed_reason_top(limit=5)
        recent_failed_reason_top = PublishTaskService.get_failed_reason_top(limit=3)

        failed_rate = today_quality_summary.get("failed_rate") or 0
        stale_queued_count = queue_health_summary.get("stale_queued_count") or 0
        stuck_running_count = len(stuck_running_tasks)
        is_worker_healthy = bool(worker_health.get("is_healthy"))

        # 每个检查项都带上跳转入口，方便运营从自检页直接进入对应排障页面。
        check_items = [
            {
                "name": "后台执行器心跳",
                "is_ok": is_worker_healthy,
                "level": "success" if is_worker_healthy else "warning",
                "summary": "正常运行" if is_worker_healthy else "疑似异常",
                "detail": f"最近轮询时间：{worker_health.get('last_run_at') or '-'}",
                "action_text": "",
                "action_url": "",
            },
            {
                "name": "排队积压",
                "is_ok": stale_queued_count == 0,
                "level": "success" if stale_queued_count == 0 else "warning",
                "summary": "无积压" if stale_queued_count == 0 else f"{stale_queued_count} 个疑似积压",
                "detail": "检查超过 10 分钟仍处于排队中的任务",
                "action_text": "查看积压任务" if stale_queued_count > 0 else "查看队列",
                "action_url": "/publish-tasks?stale_queued=1" if stale_queued_count > 0 else "/publish-tasks?status=queued",
            },
            {
                "name": "执行中卡住",
                "is_ok": stuck_running_count == 0,
                "level": "success" if stuck_running_count == 0 else "warning",
                "summary": "无卡住任务" if stuck_running_count == 0 else f"{stuck_running_count} 个疑似卡住",
                "detail": "检查超过 10 分钟未更新的执行中任务",
                "action_text": "查看执行中任务",
                "action_url": "/publish-tasks?status=running",
            },
            {
                "name": "今日失败率",
                "is_ok": failed_rate <= 10,
                "level": "success" if failed_rate <= 10 else "danger",
                "summary": f"{failed_rate}%",
                "detail": f"今日成功 {today_quality_summary.get('success_count', 0)} 个，失败 {today_quality_summary.get('failed_count', 0)} 个",
                "action_text": "查看失败任务" if failed_rate > 0 else "",
                "action_url": "/publish-tasks?status=failed" if failed_rate > 0 else "",
            },
        ]

        # 汇总级别优先展示严重异常，其次展示需要关注的问题。
        if any(item["level"] == "danger" for item in check_items):
            overall_level = "danger"
            overall_text = "存在严重异常"
        elif any(item["level"] == "warning" for item in check_items):
            overall_level = "warning"
            overall_text = "存在需要关注的问题"
        else:
            overall_level = "success"
            overall_text = "系统运行正常"

        return {
            "overall_level": overall_level,
            "overall_text": overall_text,
            "check_items": check_items,
            "worker_health": worker_health,
            "queue_health_summary": queue_health_summary,
            "stuck_running_count": stuck_running_count,
            "today_quality_summary": today_quality_summary,
            "today_failed_reason_top": today_failed_reason_top,
            "recent_failed_reason_top": recent_failed_reason_top,
        }

    @staticmethod
    def get_system_event_timeline(limit: int = 10) -> list[dict]:
        """获取系统事件时间线。"""
        # 对展示数量做轻量保护，避免页面一次展示过多事件。
        safe_limit = max(1, min(limit or 10, 20))
        events = PublishTaskService._read_system_events()
        events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        enriched_events = PublishTaskService.enrich_system_events_with_duration(events)
        return enriched_events[:safe_limit]

    @staticmethod
    def _parse_event_time(event_time_str: str) -> datetime | None:
        """解析系统事件时间。"""
        try:
            return datetime.strptime(event_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def _format_duration_seconds(seconds: int) -> str:
        """格式化持续时长。"""
        safe_seconds = max(0, seconds or 0)
        if safe_seconds < 60:
            return f"{safe_seconds} 秒"

        if safe_seconds < 3600:
            return f"{safe_seconds // 60} 分钟"

        hours = safe_seconds // 3600
        minutes = (safe_seconds % 3600) // 60
        return f"{hours} 小时 {minutes} 分钟"

    @staticmethod
    def _infer_event_group(title: str) -> str:
        """根据事件标题推断事件分组。"""
        safe_title = (title or "").strip()

        if "Worker" in safe_title or "后台执行器" in safe_title:
            return "后台执行器"

        if "积压任务" in safe_title:
            return "队列"

        if "卡住任务" in safe_title:
            return "卡住任务"

        if "失败率" in safe_title:
            return "失败率"

        return "其他"

    @staticmethod
    def _localize_event_text(text: str) -> str:
        """将历史事件中的技术英文转成中文展示。"""
        safe_text = text or ""
        replacements = {
            "Worker ": "后台执行器",
            "Worker": "后台执行器",
            "TOP5": "前5",
            "TOP 5": "前5",
            "TOP3": "前3",
            "TOP 3": "前3",
            "queued": "排队中",
            "running": "执行中",
            "success": "成功",
            "failed": "失败",
        }
        for source_text, target_text in replacements.items():
            safe_text = safe_text.replace(source_text, target_text)
        return safe_text

    @staticmethod
    def enrich_system_events_with_duration(events: list[dict]) -> list[dict]:
        """为恢复事件动态补充异常持续时长。"""
        recovery_to_alert_title = {
            "后台执行器刚刚恢复正常": "后台执行器疑似异常",
            "Worker 刚刚恢复正常": "Worker 疑似异常",
            "积压任务已清空": "存在疑似积压任务",
            "卡住任务已恢复": "存在疑似卡住任务",
            "今日失败率已恢复正常": "今日失败率偏高",
        }

        enriched_events = [dict(event) for event in events]

        for recovery_event in enriched_events:
            recovery_event["title"] = PublishTaskService._localize_event_text(
                recovery_event.get("title", "")
            )
            recovery_event["message"] = PublishTaskService._localize_event_text(
                recovery_event.get("message", "")
            )
            recovery_event["duration_text"] = ""
            recovery_event["event_group"] = PublishTaskService._infer_event_group(
                recovery_event.get("title", "")
            )
            if recovery_event.get("type") != "recovery":
                continue

            alert_title = recovery_to_alert_title.get(recovery_event.get("title", ""))
            if not alert_title:
                continue

            recovery_time = PublishTaskService._parse_event_time(recovery_event.get("created_at", ""))
            if not recovery_time:
                continue

            matched_alert_time = None
            for candidate_event in enriched_events:
                if candidate_event.get("type") != "alert":
                    continue
                candidate_title = PublishTaskService._localize_event_text(
                    candidate_event.get("title", "")
                )
                if candidate_title != PublishTaskService._localize_event_text(alert_title):
                    continue

                alert_time = PublishTaskService._parse_event_time(candidate_event.get("created_at", ""))
                if not alert_time or alert_time > recovery_time:
                    continue

                # 事件列表按时间倒序，遇到的第一条符合条件告警就是最近一次对应告警。
                matched_alert_time = alert_time
                break

            if matched_alert_time:
                duration_seconds = int((recovery_time - matched_alert_time).total_seconds())
                recovery_event["duration_text"] = f"持续 {PublishTaskService._format_duration_seconds(duration_seconds)}"

        return enriched_events

    @staticmethod
    def get_queue_health_summary() -> dict:
        """获取发布任务队列的轻量健康摘要。"""
        conn = get_db()
        try:
            # 统计当前排队中的任务数量，用于判断是否存在明显积压。
            queued_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE status=?",
                (TASK_STATUS_QUEUED,),
            )[0]

            # 统计当前执行中的任务数量，用于判断是否存在执行中卡住的风险。
            running_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE status=?",
                (TASK_STATUS_RUNNING,),
            )[0]

            # 统计今日失败任务数量，用于快速观察当天失败趋势。
            failed_today_count = PublishTaskService._fetchone(
                conn,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=%s AND DATE(updated_at)=CURDATE()
                """,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=? AND DATE(updated_at)=DATE('now','localtime')
                """,
                (TASK_STATUS_FAILED,),
            )[0]

            # 获取最早一条排队任务的创建时间，用于辅助判断排队是否过久。
            oldest_queued_row = PublishTaskService._fetchone(
                conn,
                """
                SELECT created_at
                FROM publish_tasks
                WHERE status=%s
                ORDER BY created_at ASC
                LIMIT 1
                """,
                """
                SELECT created_at
                FROM publish_tasks
                WHERE status=?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (TASK_STATUS_QUEUED,),
            )

            # 统计超过 10 分钟仍处于排队中的任务数，作为疑似积压指标。
            stale_queued_count = PublishTaskService._fetchone(
                conn,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=%s AND created_at <= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)
                """,
                """
                SELECT COUNT(*)
                FROM publish_tasks
                WHERE status=? AND created_at <= datetime('now','localtime','-10 minutes')
                """,
                (TASK_STATUS_QUEUED,),
            )[0]

            return {
                "queued_count": queued_count or 0,
                "running_count": running_count or 0,
                "failed_today_count": failed_today_count or 0,
                "oldest_queued_created_at": oldest_queued_row["created_at"] if oldest_queued_row else "",
                "stale_queued_count": stale_queued_count or 0,
            }
        finally:
            conn.close()

    @staticmethod
    def get_worker_health() -> dict:
        """获取 worker 最近一次轮询的健康状态。"""
        # 默认返回异常态，避免心跳文件缺失时误判为正常。
        result = {
            "last_run_at": "",
            "seconds_ago": 0,
            "is_healthy": False,
        }

        # 心跳文件不存在时直接返回默认值，表示还未检测到轮询记录。
        if not os.path.exists(WORKER_HEARTBEAT_FILE_PATH):
            return result

        try:
            with open(WORKER_HEARTBEAT_FILE_PATH, "r", encoding="utf-8") as heartbeat_file:
                heartbeat_data = json.load(heartbeat_file)

            last_run_at = (heartbeat_data.get("last_run_at", "") or "").strip()
            if not last_run_at:
                return result

            # 将心跳时间转换为秒差，用于判断是否超过 2 分钟未更新。
            last_run_time = datetime.strptime(last_run_at, "%Y-%m-%d %H:%M:%S")
            seconds_ago = max(0, int((datetime.now() - last_run_time).total_seconds()))

            result["last_run_at"] = last_run_at
            result["seconds_ago"] = seconds_ago
            result["is_healthy"] = seconds_ago <= 120
            return result
        except Exception:
            # 心跳文件损坏或解析失败时返回异常态，避免影响页面主流程。
            return result

    @staticmethod
    def get_failed_reason_top(limit: int = 3) -> list[dict]:
        """获取最近失败原因的聚合统计。"""
        conn = get_db()
        try:
            # 对返回数量做轻量保护，避免页面一次展示过多失败原因。
            safe_limit = max(1, min(limit or 3, 10))

            # 直接按原始错误文本聚合失败原因，空值忽略，逻辑简单且稳定。
            rows = PublishTaskService._fetchall(
                conn,
                """
                SELECT error_message AS reason, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=%s AND error_message IS NOT NULL AND TRIM(error_message) != ''
                GROUP BY error_message
                ORDER BY count DESC, MAX(id) DESC
                LIMIT %s
                """,
                """
                SELECT error_message AS reason, COUNT(*) AS count
                FROM publish_tasks
                WHERE status=? AND error_message IS NOT NULL AND TRIM(error_message) != ''
                GROUP BY error_message
                ORDER BY count DESC, MAX(id) DESC
                LIMIT ?
                """,
                (TASK_STATUS_FAILED, safe_limit),
            )

            # 统一转为简单字典列表，便于模板直接渲染。
            return [
                {
                    "reason": row["reason"],
                    "count": row["count"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_article_task_summary(article_id: int) -> dict:
        """获取单篇文章的历史任务概览数据。"""
        conn = get_db()
        try:
            # 统计该文章的任务总数、成功数和失败数，便于运营快速把握整体情况。
            total_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=?",
                (article_id,),
            )[0]
            success_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=%s AND status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=? AND status=?",
                (article_id, TASK_STATUS_SUCCESS),
            )[0]
            failed_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=%s AND status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=? AND status=?",
                (article_id, TASK_STATUS_FAILED),
            )[0]

            # 最近一次状态按任务ID倒序取最新记录。
            latest_status_row = PublishTaskService._fetchone(
                conn,
                """
                SELECT status
                FROM publish_tasks
                WHERE article_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                """
                SELECT status
                FROM publish_tasks
                WHERE article_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id,),
            )

            # 最近成功时间取最新成功任务的更新时间。
            latest_success_row = PublishTaskService._fetchone(
                conn,
                """
                SELECT updated_at
                FROM publish_tasks
                WHERE article_id=%s AND status=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                """
                SELECT updated_at
                FROM publish_tasks
                WHERE article_id=? AND status=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id, TASK_STATUS_SUCCESS),
            )

            # 最近失败原因取最新失败任务的错误信息，空值时返回空字符串。
            latest_failed_row = PublishTaskService._fetchone(
                conn,
                """
                SELECT error_message
                FROM publish_tasks
                WHERE article_id=%s AND status=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                """
                SELECT error_message
                FROM publish_tasks
                WHERE article_id=? AND status=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id, TASK_STATUS_FAILED),
            )

            latest_status = latest_status_row["status"] if latest_status_row else ""

            return {
                "total_count": total_count or 0,
                "success_count": success_count or 0,
                "failed_count": failed_count or 0,
                "latest_status": latest_status,
                "latest_status_label": PublishTaskService.get_task_status_meta(latest_status)["label"] if latest_status else "",
                "latest_success_time": latest_success_row["updated_at"] if latest_success_row else "",
                "latest_failed_reason": latest_failed_row["error_message"] if latest_failed_row and latest_failed_row["error_message"] else "",
            }
        finally:
            conn.close()

    @staticmethod
    def get_article_publish_risk(article_id: int) -> dict:
        """获取单篇文章的重复发布风险提示。"""
        conn = get_db()
        try:
            # 风险判断仅基于任务总数和成功次数，保持规则简单稳定。
            total_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=?",
                (article_id,),
            )[0]
            success_count = PublishTaskService._fetchone(
                conn,
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=%s AND status=%s",
                "SELECT COUNT(*) FROM publish_tasks WHERE article_id=? AND status=?",
                (article_id, TASK_STATUS_SUCCESS),
            )[0]

            has_risk = False
            message = ""

            # 成功发布多次属于更高风险，优先给出更明确提醒。
            if success_count >= 2:
                has_risk = True
                message = "该文章已成功发布多次，请确认是否重复推送"
            elif total_count >= 2:
                has_risk = True
                message = "该文章存在多次发布任务记录，请确认是否重复操作"

            return {
                "has_risk": has_risk,
                "total_count": total_count or 0,
                "success_count": success_count or 0,
                "message": message,
            }
        finally:
            conn.close()

    @staticmethod
    def get_latest_task_for_article(article_id: int, task_type: str = TASK_TYPE_WECHAT_DRAFT):
        """获取文章最近一次指定类型的发布任务。"""
        conn = get_db()
        try:
            # 按创建顺序倒序获取最新任务，便于后续排查和重试。
            task = PublishTaskService._fetchone(
                conn,
                """
                SELECT *
                FROM publish_tasks
                WHERE article_id=%s AND task_type=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                """
                SELECT *
                FROM publish_tasks
                WHERE article_id=? AND task_type=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id, task_type),
            )
            return dict(task) if task else None
        finally:
            conn.close()

    @staticmethod
    def create_task_for_article(
        article_id: int,
        channel: str = TASK_CHANNEL_WECHAT,
        task_type: str = TASK_TYPE_WECHAT_DRAFT,
        max_retries: int = 3,
    ) -> int:
        """为文章创建发布任务，若已有有效任务则直接复用。"""
        conn = get_db()
        try:
            # 先查文章，确保任务快照来源稳定。
            article = PublishTaskService._fetchone(
                conn,
                "SELECT * FROM articles WHERE id=%s",
                "SELECT * FROM articles WHERE id=?",
                (article_id,),
            )
            if not article:
                raise ValueError("文章不存在")

            # 避免重复创建同类有效任务，保持轻量约束。
            existing = PublishTaskService._fetchone(
                conn,
                """
                SELECT id
                FROM publish_tasks
                WHERE article_id=%s AND task_type=%s AND status IN (%s, %s)
                ORDER BY id DESC
                LIMIT 1
                """,
                """
                SELECT id
                FROM publish_tasks
                WHERE article_id=? AND task_type=? AND status IN (?, ?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id, task_type, TASK_STATUS_QUEUED, TASK_STATUS_RUNNING),
            )
            if existing:
                return existing["id"]

            # 保存文章快照，便于后续异步化时独立执行。
            payload_snapshot = json.dumps(dict(article), ensure_ascii=False)
            cursor = PublishTaskService._execute(
                conn,
                """
                INSERT INTO publish_tasks
                (article_id, channel, task_type, status, retry_count, max_retries, payload_snapshot, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                """
                INSERT INTO publish_tasks
                (article_id, channel, task_type, status, retry_count, max_retries, payload_snapshot, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                """,
                (
                    article_id,
                    channel,
                    task_type,
                    TASK_STATUS_QUEUED,
                    0,
                    max_retries,
                    payload_snapshot,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def execute_task(task_id: int) -> dict:
        """同步执行发布任务，保持当前对外仍是立即完成的体验。"""
        conn = get_db()
        try:
            # 查询任务本体，任务不存在时直接返回失败结果。
            task = PublishTaskService._fetchone(
                conn,
                "SELECT * FROM publish_tasks WHERE id=%s",
                "SELECT * FROM publish_tasks WHERE id=?",
                (task_id,),
            )
            if not task:
                return {"ok": False, "msg": "任务不存在"}

            # 超过最大重试次数的失败任务不再继续执行。
            if task["status"] == TASK_STATUS_FAILED and task["retry_count"] >= task["max_retries"]:
                return {"ok": False, "msg": "任务已超过最大重试次数"}

            # 查询最新文章数据，保证同步执行时读取到最新审核状态。
            article = PublishTaskService._fetchone(
                conn,
                "SELECT * FROM articles WHERE id=%s",
                "SELECT * FROM articles WHERE id=?",
                (task["article_id"],),
            )
            if not article:
                PublishTaskService.mark_task_failed(task_id, "文章不存在")
                return {"ok": False, "msg": "文章不存在"}

            # 将任务标记为执行中，方便后续异步化接入调度器。
            cursor = PublishTaskService._execute(
                conn,
                """
                UPDATE publish_tasks
                SET status=%s, updated_at=CURRENT_TIMESTAMP, executed_at=CURRENT_TIMESTAMP
                WHERE id=%s AND status=%s
                """,
                """
                UPDATE publish_tasks
                SET status=?, updated_at=datetime('now','localtime'), executed_at=datetime('now','localtime')
                WHERE id=? AND status=?
                """,
                (TASK_STATUS_RUNNING, task_id, TASK_STATUS_QUEUED),
            )
            if cursor.rowcount != 1:
                return {"ok": False, "msg": "任务已被其他执行器处理"}
            conn.commit()
        finally:
            conn.close()

        try:
            # 继续复用现有微信发布能力，不改变核心推送逻辑。
            media_id = publish_single_article(dict(article))
            if media_id:
                PublishTaskService.mark_task_success(task_id, external_draft_id=media_id)
                return {"ok": True, "draft_id": media_id}

            # 发布返回空结果时仅标记任务失败，不改文章已审核状态。
            PublishTaskService.mark_task_failed(task_id, "推送失败，请检查微信API配置")
            return {"ok": False, "msg": "推送失败，请检查微信API配置"}
        except Exception as e:
            # 保留异常信息，便于后续重试或任务排查。
            PublishTaskService.mark_task_failed(task_id, str(e))
            return {"ok": False, "msg": str(e), "is_exception": True}

    @staticmethod
    def mark_task_success(task_id: int, external_draft_id: str = "", external_publish_id: str = ""):
        """标记任务成功，并回写文章草稿状态。"""
        conn = get_db()
        try:
            task = PublishTaskService._fetchone(
                conn,
                "SELECT article_id FROM publish_tasks WHERE id=%s",
                "SELECT article_id FROM publish_tasks WHERE id=?",
                (task_id,),
            )
            if not task:
                return

            # 执行成功后回写任务结果，便于后续做审计与重试控制。
            result_payload = json.dumps(
                {
                    "external_draft_id": external_draft_id,
                    "external_publish_id": external_publish_id,
                },
                ensure_ascii=False,
            )
            PublishTaskService._execute(
                conn,
                """
                UPDATE publish_tasks
                SET status=%s, result_payload=%s, external_draft_id=%s, external_publish_id=%s, error_message='',
                    updated_at=CURRENT_TIMESTAMP, executed_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                """
                UPDATE publish_tasks
                SET status=?, result_payload=?, external_draft_id=?, external_publish_id=?, error_message='',
                    updated_at=datetime('now','localtime'), executed_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    TASK_STATUS_SUCCESS,
                    result_payload,
                    external_draft_id,
                    external_publish_id,
                    task_id,
                ),
            )

            # 文章继续走旧 status + 新拆分字段双写，保证兼容行为不变。
            review_status, publish_status = split_legacy_status(STATUS_DRAFT_SENT)
            PublishTaskService._execute(
                conn,
                """
                UPDATE articles
                SET status=%s, review_status=%s, publish_status=%s, draft_id=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                """
                UPDATE articles
                SET status=?, review_status=?, publish_status=?, draft_id=?, updated_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    STATUS_DRAFT_SENT,
                    review_status,
                    publish_status,
                    external_draft_id,
                    task["article_id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def mark_task_failed(task_id: int, error_message: str):
        """标记任务失败，但暂不改变文章已审核的外部表现。"""
        conn = get_db()
        try:
            task = PublishTaskService._fetchone(
                conn,
                "SELECT retry_count, max_retries FROM publish_tasks WHERE id=%s",
                "SELECT retry_count, max_retries FROM publish_tasks WHERE id=?",
                (task_id,),
            )
            if not task:
                return

            # 每次失败都正确累加重试次数，便于后续重试控制。
            next_retry_count = (task["retry_count"] or 0) + 1

            # 当前阶段仅回写任务失败信息，为后续异步重试做准备。
            result_payload = json.dumps(
                {
                    "error_message": error_message,
                    "retry_count": next_retry_count,
                },
                ensure_ascii=False,
            )
            PublishTaskService._execute(
                conn,
                """
                UPDATE publish_tasks
                SET status=%s, retry_count=%s, result_payload=%s, error_message=%s, updated_at=CURRENT_TIMESTAMP,
                    executed_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                """
                UPDATE publish_tasks
                SET status=?, retry_count=?, result_payload=?, error_message=?, updated_at=datetime('now','localtime'),
                    executed_at=datetime('now','localtime')
                WHERE id=?
                """,
                (
                    TASK_STATUS_FAILED,
                    next_retry_count,
                    result_payload,
                    error_message,
                    task_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def retry_task(task_id: int) -> dict:
        """重试失败的发布任务。"""
        conn = get_db()
        try:
            task = PublishTaskService._fetchone(
                conn,
                "SELECT * FROM publish_tasks WHERE id=%s",
                "SELECT * FROM publish_tasks WHERE id=?",
                (task_id,),
            )
            if not task:
                return {"ok": False, "msg": "任务不存在"}

            # 仅允许失败任务进入重试流程。
            if task["status"] != TASK_STATUS_FAILED:
                return {"ok": False, "msg": "仅允许重试失败任务"}

            # 超过最大重试次数后不再继续执行。
            if task["retry_count"] >= task["max_retries"]:
                return {"ok": False, "msg": "任务已超过最大重试次数"}

            # 重试前将状态重置为排队中，便于复用现有执行逻辑。
            cursor = PublishTaskService._execute(
                conn,
                """
                UPDATE publish_tasks
                SET status=%s, error_message='', updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND status=%s
                """,
                """
                UPDATE publish_tasks
                SET status=?, error_message='', updated_at=datetime('now','localtime')
                WHERE id=? AND status=?
                """,
                (TASK_STATUS_QUEUED, task_id, TASK_STATUS_FAILED),
            )
            if cursor.rowcount != 1:
                return {"ok": False, "msg": "任务状态已变化，请刷新后重试"}
            conn.commit()
        finally:
            conn.close()

        # 直接复用现有同步执行逻辑，保持外部体验不变。
        return PublishTaskService.execute_task(task_id)
