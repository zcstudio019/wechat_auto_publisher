"""独立调度器应用。

本模块只负责 APScheduler 的创建和任务注册，不引入 Flask app。
生产环境中由 run_scheduler.py 启动；本地开发入口 main.py 也复用这里的逻辑。
"""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import PUBLISH_HOUR, PUBLISH_MINUTE, PUBLISH_SCHEDULE
from jobs.publish_worker import run_once as run_publish_worker_once
from wechat_api.publisher import publish_approved_articles

logger = logging.getLogger(__name__)


def setup_scheduler_logging():
    """初始化调度器日志，便于独立进程和本地开发共用。"""
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
    """定时发布任务：将已审核文章推送到微信公众号草稿箱。"""
    logger.info("=== 定时推送任务开始 ===")
    try:
        count = publish_approved_articles()
        logger.info("=== 定时推送完成，推送 %s 篇 ===", count)
    except Exception:
        # 调度任务不能让异常冒泡，否则会影响后续调度。
        logger.exception("定时推送异常")


def job_consume_publish_tasks():
    """后台轮询消费 queued 状态的发布任务。"""
    logger.info("=== 发布任务轮询开始 ===")
    try:
        # 每轮只处理少量任务，避免单次轮询占用过久。
        count = run_publish_worker_once(limit=5)
        logger.info("=== 发布任务轮询完成，处理 %s 个任务 ===", count)
    except Exception:
        # worker job 自身保持稳定，不影响下一分钟继续轮询。
        logger.exception("发布任务轮询异常")


def build_scheduler():
    """创建调度器并注册全部后台任务。"""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    if PUBLISH_SCHEDULE:
        for hour, minute in PUBLISH_SCHEDULE:
            job_id = f"publish_{hour:02d}{minute:02d}"
            job_name = f"定时发布 {hour:02d}:{minute:02d}"
            scheduler.add_job(
                job_publish,
                CronTrigger(hour=hour, minute=minute),
                id=job_id,
                name=job_name,
                replace_existing=True,
            )
            logger.info("  - 定时任务: %02d:%02d", hour, minute)
    else:
        # 兼容旧配置：没有多时段配置时使用单时段发布。
        scheduler.add_job(
            job_publish,
            CronTrigger(hour=PUBLISH_HOUR, minute=PUBLISH_MINUTE),
            id="daily_publish",
            name="每日发布",
            replace_existing=True,
        )
        logger.info("  - 每日推送: %02d:%02d", PUBLISH_HOUR, PUBLISH_MINUTE)

    # 每分钟轮询发布任务队列；max_instances=1 防止单进程内任务重叠。
    scheduler.add_job(
        job_consume_publish_tasks,
        "interval",
        minutes=1,
        id="publish_task_worker",
        name="发布任务轮询",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("  - 发布任务轮询: 每 1 分钟执行一次")
    return scheduler
