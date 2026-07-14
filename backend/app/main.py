"""Q宠乐斗 Backend — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, config, accounts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 尝试连接 Redis（开发环境可能未安装，容错降级）
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
async def get_weekly(accountId: str = ""):
    from datetime import date, timedelta
    from app.core.database import get_db
    from sqlalchemy import select
    from app.models.daily_record import DailyRecord

    async for db in get_db():
        today = date.today()
        start = today - timedelta(days=7)
        result = await db.execute(
            select(DailyRecord)
            .where(DailyRecord.account_id == accountId, DailyRecord.date >= start)
            .order_by(DailyRecord.date)
        )
        records = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "date": str(r.date), "level": r.level, "class_name": r.class_name,
                    "combat_power": r.combat_power, "npc_fights": r.npc_fights,
                    "tower_floors": r.tower_floors, "tower_max": r.tower_max,
                    "harvests": r.harvests, "plants": r.plants, "steals": r.steals,
                    "waters": r.waters, "digs": r.digs, "land_upgrades": r.land_upgrades,
                    "today_harvest_exp": r.today_harvest_exp, "current_exp": r.current_exp,
                    "exp_battle": r.exp_battle,
                }
                for r in records
            ],
        }
