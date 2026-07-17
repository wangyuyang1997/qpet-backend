"""全局调度器 — APScheduler cron + 每账号 interval"""
import asyncio
import logging
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.core.logger import info, warn

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_running = False


def start():
    global _running
    if _running:
        return
    scheduler.start()
    _running = True
    info("系统", "调度器", "全局调度器已启动")


def shutdown():
    global _running
    if _running:
        scheduler.shutdown(wait=False)
        _running = False
        info("系统", "调度器", "全局调度器已关闭")


def register_cron(callback, cron_expr: str, job_id: str, jitter: int = 0):
    """注册 cron 定时任务"""
    minute, hour, dom, month, dow = cron_expr.split()
    scheduler.add_job(
        callback,
        CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow, jitter=jitter),
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"注册cron任务: {job_id} ({cron_expr})")


def register_interval(callback, seconds: int, job_id: str, jitter: int = 0):
    """注册间隔定时任务"""
    scheduler.add_job(
        callback,
        IntervalTrigger(seconds=seconds, jitter=jitter),
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"注册interval任务: {job_id} ({seconds}s)")


def remove_job(job_id: str):
    try:
        scheduler.remove_job(job_id)
        logger.info(f"移除定时任务: {job_id}")
    except Exception as e:
        warn("系统", "调度器", f"移除任务失败: {job_id} {e}")
