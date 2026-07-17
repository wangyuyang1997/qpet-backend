"""Q宠乐斗 Backend — FastAPI 入口"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, config, accounts, logs

logger = logging.getLogger("qpet.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 尝试连接 Redis
    try:
        from app.core.redis import init_redis
        await init_redis()
    except Exception:
        pass

    # 尝试连接 RabbitMQ
    try:
        from app.core.rabbitmq import init_rabbitmq
        await init_rabbitmq()
    except Exception:
        pass

    # 恢复 running=1 的引擎
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.account import Account
        from app.services.engine import get_or_create_engine
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Account.id).where(Account.running == 1))
            running_ids = [row[0] for row in r.fetchall()]
        for aid in running_ids:
            engine = await get_or_create_engine(aid)
            if engine:
                asyncio.create_task(engine.start())
    except Exception as e:
        logger.warning(f"恢复引擎失败: {e}")

    # 启动调度器 + 日志日切
    try:
        from app.services.scheduler import scheduler, register_cron, start as start_scheduler
        from app.core.logger import migrate_logs_to_history
        start_scheduler()
        register_cron(migrate_logs_to_history, "2 0 * * *", "log_migration", jitter=30)
        # 启动时立即执行一次日切（处理重启间隔内的旧日志）
        import asyncio as _asyncio
        _asyncio.get_event_loop().run_in_executor(None, migrate_logs_to_history)
        logger.info("日志日切定时任务已注册 (每日00:02)")
    except Exception as e:
        logger.warning(f"启动日志日切失败: {e}")

    yield

    try:
        from app.services.scheduler import shutdown as stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    try:
        from app.core.redis import close_redis
        await close_redis()
    except Exception:
        pass

    try:
        from app.core.rabbitmq import close_rabbitmq
        await close_rabbitmq()
    except Exception:
        pass


app = FastAPI(
    title="Q宠乐斗 API",
    description="前后端分离重构 v5.0",
    version="5.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(accounts.router)
app.include_router(logs.router)


@app.get("/api/version", response_model=dict)
async def get_version():
    from datetime import datetime
    return {"version": f"v5.0-{datetime.now().strftime('%Y%m%d%H%M')}"}


@app.get("/api/status")
async def get_status():
    from app.services.engine import _engines
    running = sum(1 for e in _engines.values() if e._running)
    return {
        "success": True,
        "data": {
            "total_accounts": len(_engines),
            "running": running,
            "version": f"v5.0-{__import__('datetime').datetime.now().strftime('%Y%m%d%H%M')}",
        },
    }


@app.get("/api/dashboard/weekly")
async def get_weekly(accountId: str = "",
                     user: dict = __import__('fastapi').Depends(
                         __import__('app.core.auth_middleware', fromlist=['get_current_user']).get_current_user)):
    from datetime import date, timedelta
    from app.core.database import get_db
    from sqlalchemy import select
    from app.models.daily_record import DailyRecord
    from app.models.user import UserAccount
    from app.core.redis import cache_get, cache_set
    import json

    # Check Redis cache first
    cache_key = f"qpet:dashboard:weekly:{accountId}"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    async for db in get_db():
        today = date.today()
        user_id = user.get("user_id") or user.get("userId")
        role = user.get("role", "")
        bound_ids: set[str] | None = None
        if role != "admin" and user_id:
            r = await db.execute(select(UserAccount.account_id).where(UserAccount.user_id == user_id))
            bound_ids = {row[0] for row in r.fetchall()}

        # Fetch this account's 7-day records
        start = today - timedelta(days=7)
        result = await db.execute(
            select(DailyRecord)
            .where(DailyRecord.account_id == accountId, DailyRecord.date >= start)
            .order_by(DailyRecord.date)
        )
        records = result.scalars().all()

        # Lightweight summary query — only aggregates, not full rows
        week_start = today - timedelta(days=6)
        summary = {"total_exp": 0, "total_contrib": 0, "total_steals": 0, "total_accounts": 0}
        if bound_ids is not None:
            summary["total_accounts"] = len(bound_ids)
            summary_result = await db.execute(
                select(
                    __import__('sqlalchemy').func.sum(DailyRecord.today_harvest_exp),
                    __import__('sqlalchemy').func.sum(DailyRecord.gang_contribution),
                    __import__('sqlalchemy').func.sum(DailyRecord.steals),
                ).where(DailyRecord.date >= week_start, DailyRecord.account_id.in_(bound_ids))
            )
        else:
            cnt_result = await db.execute(
                select(__import__('sqlalchemy').func.count(__import__('sqlalchemy').func.distinct(DailyRecord.account_id)))
                .where(DailyRecord.date >= week_start)
            )
            summary["total_accounts"] = cnt_result.scalar() or 0
            summary_result = await db.execute(
                select(
                    __import__('sqlalchemy').func.sum(DailyRecord.today_harvest_exp),
                    __import__('sqlalchemy').func.sum(DailyRecord.gang_contribution),
                    __import__('sqlalchemy').func.sum(DailyRecord.steals),
                ).where(DailyRecord.date >= week_start)
            )
        row = summary_result.fetchone()
        if row:
            summary["total_exp"] = row[0] or 0
            summary["total_contrib"] = row[1] or 0
            summary["total_steals"] = row[2] or 0

        resp = {
            "success": True,
            "data": [
                {
                    "date": str(r.date), "level": r.level, "class_name": r.class_name,
                    "combat_power": r.combat_power, "npc_fights": r.npc_fights,
                    "tower_floors": r.tower_floors, "tower_max": r.tower_max,
                    "harvests": r.harvests, "plants": r.plants, "steals": r.steals,
                    "waters": r.waters, "digs": r.digs, "land_upgrades": r.land_upgrades,
                    "stamina_ads": r.stamina_ads, "community_ads": r.community_ads,
                    "farm_ads": r.farm_ads,
                    "level_exp": r.level_exp, "level_exp_max": r.level_exp_max,
                    "gang_contribution": r.gang_contribution, "gang_boss_fights": r.gang_boss_fights, "gang_challenge_books": r.gang_challenge_books, "tower_revive": r.tower_revive, "flowers_remaining": r.flowers_remaining,
                    "abyss_tickets": r.abyss_tickets,
                    "today_harvest_exp": r.today_harvest_exp, "current_exp": r.current_exp,
                    "exp_battle": r.exp_battle, "challenge_books": r.challenge_books,
                    "flowers_sent": r.flowers_sent,
                }
                for r in records
            ],
            "summary": summary,
        }
        await cache_set(cache_key, json.dumps(resp), 180)
        return resp


@app.get("/api/dashboard/weekly-all")
async def get_weekly_all(
    user: dict = __import__('fastapi').Depends(
        __import__('app.core.auth_middleware', fromlist=['get_current_user']).get_current_user)):
    """一次返回所有绑定账号的7天数据+汇总，替代N次单独请求"""
    from datetime import date, timedelta
    from app.core.database import get_db
    from sqlalchemy import select, func
    from app.models.daily_record import DailyRecord
    from app.models.user import UserAccount
    from app.core.redis import cache_get, cache_set
    import json

    cache_key = "qpet:dashboard:weekly-all"
    cached = await cache_get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass

    async for db in get_db():
        today = date.today()
        user_id = user.get("user_id") or user.get("userId")
        role = user.get("role", "")
        bound_ids: set[str] | None = None
        if role != "admin" and user_id:
            r = await db.execute(select(UserAccount.account_id).where(UserAccount.user_id == user_id))
            bound_ids = {row[0] for row in r.fetchall()}

        week_start = today - timedelta(days=6)
        # Single query: all records for bound accounts in last 7 days
        q = select(DailyRecord).where(DailyRecord.date >= week_start)
        if bound_ids is not None:
            q = q.where(DailyRecord.account_id.in_(bound_ids))
        result = await db.execute(q.order_by(DailyRecord.account_id, DailyRecord.date))
        all_records = result.scalars().all()

        # Group by account_id
        by_account: dict[str, list] = {}
        for rec in all_records:
            by_account.setdefault(rec.account_id, []).append(rec)

        # Summary from single aggregation query
        sq = select(
            func.sum(DailyRecord.today_harvest_exp),
            func.sum(DailyRecord.gang_contribution),
            func.sum(DailyRecord.steals),
            func.count(func.distinct(DailyRecord.account_id)),
        ).where(DailyRecord.date >= week_start)
        if bound_ids is not None:
            sq = sq.where(DailyRecord.account_id.in_(bound_ids))
        srow = (await db.execute(sq)).fetchone()
        summary = {
            "total_exp": srow[0] or 0,
            "total_contrib": srow[1] or 0,
            "total_steals": srow[2] or 0,
            "total_accounts": srow[3] or 0,
        }

        resp = {
            "success": True,
            "data": {
                aid: [
                    {
                        "date": str(r.date), "level": r.level, "class_name": r.class_name,
                        "combat_power": r.combat_power, "npc_fights": r.npc_fights,
                        "tower_floors": r.tower_floors, "tower_max": r.tower_max,
                        "harvests": r.harvests, "plants": r.plants, "steals": r.steals,
                        "waters": r.waters, "digs": r.digs, "land_upgrades": r.land_upgrades,
                        "stamina_ads": r.stamina_ads, "community_ads": r.community_ads,
                        "farm_ads": r.farm_ads,
                        "level_exp": r.level_exp, "level_exp_max": r.level_exp_max,
                        "gang_contribution": r.gang_contribution, "gang_boss_fights": r.gang_boss_fights, "gang_challenge_books": r.gang_challenge_books, "tower_revive": r.tower_revive, "flowers_remaining": r.flowers_remaining,
                        "abyss_tickets": r.abyss_tickets,
                        "today_harvest_exp": r.today_harvest_exp, "current_exp": r.current_exp,
                        "exp_battle": r.exp_battle, "challenge_books": r.challenge_books,
                        "flowers_sent": r.flowers_sent,
                    }
                    for r in recs
                ]
                for aid, recs in by_account.items()
            },
            "summary": summary,
        }
        await cache_set(cache_key, json.dumps(resp), 180)
        return resp
