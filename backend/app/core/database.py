"""PostgreSQL 异步连接池 — 使用 SQLAlchemy 默认值 pool_size=20, max_overflow=10"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

_log = logging.getLogger("qpet.db")

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_log.info(f"PG pool using defaults: pool_size=20 max_overflow=10")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
