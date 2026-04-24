"""轻量发布任务轮询执行器。"""

import json
import logging
import os
from datetime import datetime

from database import get_db, is_mysql
from services.publish_task_service import PublishTaskService, TASK_STATUS_QUEUED

logger = logging.getLogger(__name__)

# 控制每轮最多处理的任务数，避免单次轮询占用过久。
DEFAULT_FETCH_LIMIT = 5

# 统一定义 worker 心跳文件路径，便于前端页面做轻量健康检查。
HEARTBEAT_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "worker_heartbeat.json",
)


def update_worker_heartbeat():
    """更新 worker 最近一次轮询时间。"""
    # 每次轮询开始时刷新心跳文件，便于页面判断后台执行器是否仍在工作。
    os.makedirs(os.path.dirname(HEARTBEAT_FILE_PATH), exist_ok=True)
    with open(HEARTBEAT_FILE_PATH, "w", encoding="utf-8") as heartbeat_file:
        json.dump(
            {
                "last_run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            heartbeat_file,
            ensure_ascii=False,
        )


def fetch_queued_tasks(limit: int = DEFAULT_FETCH_LIMIT) -> list[int]:
    """获取待执行的发布任务ID列表。"""
    conn = get_db()
    try:
        # 只拉取 queued 状态任务，显式区分 SQLite / MySQL 占位符。
        if is_mysql():
            rows = conn.execute(
                """
                SELECT id
                FROM publish_tasks
                WHERE status=%s
                ORDER BY id ASC
                LIMIT %s
                """,
                (TASK_STATUS_QUEUED, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id
                FROM publish_tasks
                WHERE status=?
                ORDER BY id ASC
                LIMIT ?
                """,
                (TASK_STATUS_QUEUED, limit),
            ).fetchall()
        return [row["id"] for row in rows]
    finally:
        conn.close()


def run_once(limit: int = DEFAULT_FETCH_LIMIT) -> int:
    """执行一轮发布任务消费。"""
    # 轮询开始即记录一次心跳，便于外部页面判断 worker 是否健康。
    update_worker_heartbeat()

    # 每轮最多处理固定数量任务，避免后台轮询压垮主进程。
    task_ids = fetch_queued_tasks(limit=limit)
    if not task_ids:
        return 0

    handled = 0
    for task_id in task_ids:
        try:
            # 先做一次存在性检查，跳过不存在或非法任务。
            task = PublishTaskService.get_task(task_id)
            if not task:
                logger.warning(f"[PublishWorker] 任务不存在，已跳过: task_id={task_id}")
                continue

            # 仅处理 queued 任务，避免与同步执行中的任务冲突。
            if task.get("status") != TASK_STATUS_QUEUED:
                logger.info(f"[PublishWorker] 任务状态不是 queued，已跳过: task_id={task_id}, status={task.get('status')}")
                continue

            PublishTaskService.execute_task(task_id)
            handled += 1
        except Exception as e:
            # 轮询器本身不抛出异常，避免影响后续任务消费。
            logger.error(f"[PublishWorker] 执行任务异常: task_id={task_id}, error={e}")

    return handled
