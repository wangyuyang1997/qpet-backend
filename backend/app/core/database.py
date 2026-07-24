"""PostgreSQL 异步连接池 — 8引擎长连接 + 短连接余量"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

_log = logging.getLogger("qpet.db")

engine = create_async_engine(settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_recycle=1800,
    pool_pre_ping=True,
    pool_reset_on_return="rollback",
    echo=False)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_log.info("PG pool_size=20 max_overflow=10 recycle=1800s reset_on_return=rollback")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
