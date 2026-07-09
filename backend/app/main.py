"""Q宠乐斗 Backend — FastAPI 入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase B: DB + Redis + MQ init
    yield
    # Phase B: resource cleanup


app = FastAPI(
    title="Q宠乐斗 API",
    description="前后端分离重构 v5.0 — 接口契约",
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


@app.get("/api/version", response_model=dict)
async def get_version():
    from datetime import datetime
    return {"version": f"v5.0-{datetime.now().strftime('%Y%m%d%H%M')}"}
