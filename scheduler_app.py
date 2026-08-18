"""Independent APScheduler application for production and local reuse."""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from jobs.cover_worker import run_once as run_cover_worker_once

logger = logging.getLogger(__name__)


def setup_scheduler_logging():
    """Initialize scheduler logs for local runs and systemd services."""
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def job_consume_cover_tasks():
    """Consume queued AI cover generation tasks."""
    logger.info("=== cover task worker started ===")
    try:
        count = run_cover_worker_once(limit=2)
        logger.info("=== cover task worker finished, processed=%s ===", count)
    except Exception:
        logger.exception("cover task worker failed")


def job_scan_cultivation_customers():
    """每天刷新融资客户生命周期和跟进节点；失败不影响其他调度任务。"""
    logger.info("=== cultivation customer scan started ===")
    try:
        from services.cultivation_service import scan_cultivation_customers

        result = scan_cultivation_customers()
        logger.info("=== cultivation customer scan finished: %s ===", result)
        return result
    except Exception:
        logger.exception("cultivation customer scan failed")
        return {"scanned": 0, "tasks_created": 0, "errors": 1}


def build_scheduler():
    """Create the scheduler and register all background jobs."""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 微信草稿投递必须由后台人工按钮触发，不注册任何定时发布任务。
    scheduler.add_job(
        job_consume_cover_tasks,
        "interval",
        seconds=30,
        id="cover_task_worker",
        name="cover task worker",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("cover task worker registered")
    scheduler.add_job(
        job_scan_cultivation_customers,
        "cron",
        hour=9,
        minute=0,
        id="cultivation_daily_scan",
        name="融资客户每日到期扫描",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("cultivation daily scan registered at 09:00")
    return scheduler
