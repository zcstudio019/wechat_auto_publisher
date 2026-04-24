"""生产 Scheduler 服务入口。

该进程只运行 APScheduler，不启动 Flask Web。
适合由 systemd 单实例托管，避免 Gunicorn 多 worker 重复启动调度任务。
"""

import signal
import time

from database import init_db
from scheduler_app import build_scheduler, setup_scheduler_logging


def main():
    """启动独立调度器并保持进程存活。"""
    setup_scheduler_logging()

    # Scheduler 进程启动时初始化数据库，确保表结构存在。
    init_db()

    scheduler = build_scheduler()
    scheduler.start()

    should_stop = {"value": False}

    def request_shutdown(signum, _frame):
        """收到 systemd/终端退出信号时，标记优雅关闭。"""
        should_stop["value"] = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    try:
        while not should_stop["value"]:
            time.sleep(1)
    finally:
        # wait=False 避免 systemd 停止时长时间阻塞。
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
