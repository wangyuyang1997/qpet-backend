"""Q宠乐斗 Backend — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth


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


@app.get("/api/version", response_model=dict)
async def get_version():
    from datetime import datetime
    return {"version": f"v5.0-{datetime.now().strftime('%Y%m%d%H%M')}"}
