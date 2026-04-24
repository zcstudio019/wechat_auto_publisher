"""本地开发兼容入口。

生产部署请使用：
- run_web.py：只运行 Flask Web，供 Gunicorn 加载。
- run_scheduler.py：只运行 APScheduler，供 systemd 单独托管。

保留 main.py 是为了本地开发时仍可一键启动 Web + Scheduler。
"""

import logging
import os
import sys
import threading
import time

# 确保项目根目录在导入路径中，便于 Windows 本地直接运行。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WEB_AUTO_RELOAD, WEB_HOST, WEB_PORT
from database import init_db
from scheduler_app import build_scheduler, setup_scheduler_logging

logger = logging.getLogger(__name__)


def start_web():
    """在线程中启动 Flask Web；仅供本地开发兼容使用。"""
    from web_ui.app import app

    logger.info("Web 管理后台启动：http://%s:%s", WEB_HOST, WEB_PORT)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


def run_with_auto_reload():
    """以 Flask 热更新模式启动本地开发环境。"""
    from web_ui.app import app

    init_db()

    # Werkzeug 热更新会有父/子进程；只在真正服务进程中启动 scheduler，避免重复调度。
    scheduler = None
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = build_scheduler()
        scheduler.start()
        logger.info("调度器已启动（热更新子进程）")

    logger.info("Web 管理后台启动：http://%s:%s（热更新模式）", WEB_HOST, WEB_PORT)
    try:
        app.run(host=WEB_HOST, port=WEB_PORT, debug=True, use_reloader=True)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
            logger.info("调度器已停止（热更新子进程）")


def run_legacy_combined():
    """本地兼容模式：同一进程启动 Web 线程 + Scheduler。"""
    init_db()

    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()

    scheduler = build_scheduler()
    scheduler.start()
    logger.info("调度器已启动")
    logger.info("本地开发入口已启动，按 Ctrl+C 停止")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        logger.info("本地开发入口已停止")


def main():
    """本地开发主入口。"""
    setup_scheduler_logging()

    if WEB_AUTO_RELOAD:
        run_with_auto_reload()
        return

    run_legacy_combined()


if __name__ == "__main__":
    main()
