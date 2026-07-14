"""全局调度器 — APScheduler cron + 每账号 interval"""
import asyncio
import logging
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_running = False


def start():
    global _running
    if _running:
        return
    scheduler.start()
    _running = True
    logger.info("全局调度器已启动")


def shutdown():
    global _running
    if _running:
        scheduler.shutdown(wait=False)
        _running = False


def register_cron(callback, cron_expr: str, job_id: str, jitter: int = 0):
    """注册 cron 定时任务"""
    minute, hour, dom, month, dow = cron_expr.split()
    scheduler.add_job(
        callback,
        CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow, jitter=jitter),
        id=job_id,
        replace_existing=True,
    )


def register_interval(callback, seconds: int, job_id: str, jitter: int = 0):
    """注册间隔定时任务"""
    scheduler.add_job(
        callback,
        IntervalTrigger(seconds=seconds, jitter=jitter),
        id=job_id,
        replace_existing=True,
    )


def remove_job(job_id: str):
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
