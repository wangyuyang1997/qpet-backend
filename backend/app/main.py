"""Q宠乐斗 Backend — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, config, accounts


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
                await engine.start()
                print(f"[startup] 恢复引擎: {aid}")
    except Exception as e:
        print(f"[startup] 恢复引擎失败: {e}")

    yield

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


@app.get("/api/version", response_model=dict)
async def get_version():
    from datetime import datetime
    return {"version": f"v5.0-{datetime.now().strftime('%Y%m%d%H%M')}"}


@app.get("/api/logs/stats")
async def get_logs_stats():
    return {"success": True, "data": {"total": 0, "today": 0}}


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

    async for db in get_db():
        today = date.today()
        # Get user's bound account IDs for filtering summary
        user_id = user.get("user_id") or user.get("userId")
        role = user.get("role", "")
        bound_ids: set[str] | None = None
        if role != "admin" and user_id:
            r = await db.execute(select(UserAccount.account_id).where(UserAccount.user_id == user_id))
            bound_ids = {row[0] for row in r.fetchall()}
        start = today - timedelta(days=7)
        result = await db.execute(
            select(DailyRecord)
            .where(DailyRecord.account_id == accountId, DailyRecord.date >= start)
            .order_by(DailyRecord.date)
        )
        records = result.scalars().all()
        # Fetch past 7 days across all accounts for summary
        week_start = today - timedelta(days=6)
        all_result = await db.execute(
            select(DailyRecord)
            .where(DailyRecord.date >= week_start)
        )
        all_week = all_result.scalars().all()
        if bound_ids is not None:
            all_week = [r for r in all_week if r.account_id in bound_ids]
        total_accounts = len(bound_ids) if bound_ids else len(set(r.account_id for r in all_week))
        summary = {
            "total_exp": sum(r.today_harvest_exp for r in all_week),
            "total_contrib": sum(r.gang_contribution for r in all_week),
            "total_steals": sum(r.steals for r in all_week),
            "total_accounts": total_accounts,
        }
        return {
            "success": True,
            "data": [
                {
                    "date": str(r.date), "level": r.level, "class_name": r.class_name,
                    "combat_power": r.combat_power, "npc_fights": r.npc_fights,
                    "friend_fights": r.friend_fights, "tower_floors": r.tower_floors,
                    "tower_max": r.tower_max,
                    "harvests": r.harvests, "plants": r.plants, "steals": r.steals,
                    "waters": r.waters, "digs": r.digs, "land_upgrades": r.land_upgrades,
                    "stamina_ads": r.stamina_ads, "community_ads": r.community_ads,
                    "farm_ads": r.farm_ads,
                    "level_exp": r.level_exp, "level_exp_max": r.level_exp_max,
                    "gang_contribution": r.gang_contribution, "abyss_tickets": r.abyss_tickets,
                    "today_harvest_exp": r.today_harvest_exp, "current_exp": r.current_exp,
                    "exp_battle": r.exp_battle,
                }
                for r in records
            ],
            "summary": summary,
        }
