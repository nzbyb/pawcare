"""进程内定时任务。

目前只有一个任务：每天早上扫描 7 天内到期或已逾期的健康提醒，
为宠物主补站内通知。用户打开通知中心时仍会惰性同步一次，
所以即使服务在 08:00 没运行，也不会漏掉当天的提醒。

多进程部署时每个进程都会注册同名任务，通知的 dedupe_key 保证不会重复。
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services import notification_service

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def sync_reminders_job() -> None:
    db = SessionLocal()
    try:
        created = notification_service.sync_all_reminders(db)
        if created:
            logger.info("定时提醒同步完成：新增 %s 条通知", created)
    except Exception:
        db.rollback()
        logger.exception("定时提醒同步失败")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not settings.SCHEDULER_ENABLED or _scheduler is not None:
        return

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        sync_reminders_job,
        trigger="cron",
        hour=8,
        minute=0,
        id="sync_due_reminders",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("提醒同步任务已启动：每天 08:00 扫描健康提醒")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
