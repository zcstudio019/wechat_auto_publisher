"""Independent APScheduler application for production and local reuse."""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import PUBLISH_HOUR, PUBLISH_MINUTE, PUBLISH_SCHEDULE
from jobs.cover_worker import run_once as run_cover_worker_once
from jobs.publish_worker import run_once as run_publish_worker_once
from wechat_api.publisher import publish_approved_articles

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


def job_publish():
    """Push approved articles to the WeChat draft box on schedule."""
    logger.info("=== scheduled publish started ===")
    try:
        count = publish_approved_articles()
        logger.info("=== scheduled publish finished, processed=%s ===", count)
    except Exception:
        logger.exception("scheduled publish failed")


def job_consume_publish_tasks():
    """Consume queued publish tasks without blocking scheduler continuity."""
    logger.info("=== publish task worker started ===")
    try:
        count = run_publish_worker_once(limit=5)
        logger.info("=== publish task worker finished, processed=%s ===", count)
    except Exception:
        logger.exception("publish task worker failed")


def job_consume_cover_tasks():
    """Consume queued AI cover generation tasks."""
    logger.info("=== cover task worker started ===")
    try:
        count = run_cover_worker_once(limit=2)
        logger.info("=== cover task worker finished, processed=%s ===", count)
    except Exception:
        logger.exception("cover task worker failed")


def build_scheduler():
    """Create the scheduler and register all background jobs."""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    if PUBLISH_SCHEDULE:
        for hour, minute in PUBLISH_SCHEDULE:
            scheduler.add_job(
                job_publish,
                CronTrigger(hour=hour, minute=minute),
                id=f"publish_{hour:02d}{minute:02d}",
                name=f"scheduled publish {hour:02d}:{minute:02d}",
                replace_existing=True,
            )
            logger.info("scheduled publish registered: %02d:%02d", hour, minute)
    else:
        scheduler.add_job(
            job_publish,
            CronTrigger(hour=PUBLISH_HOUR, minute=PUBLISH_MINUTE),
            id="daily_publish",
            name="daily publish",
            replace_existing=True,
        )
        logger.info("daily publish registered: %02d:%02d", PUBLISH_HOUR, PUBLISH_MINUTE)

    scheduler.add_job(
        job_consume_publish_tasks,
        "interval",
        minutes=1,
        id="publish_task_worker",
        name="publish task worker",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("publish task worker registered")

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
    return scheduler
