"""PostgreSQL 异步连接池 — 8引擎长连接 + 短连接余量"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

_log = logging.getLogger("qpet.db")

# 8 个引擎各持 1 个长连接(self.db)，每周期 FarmSync/GangSync 临时借 1-2 个。
# pool=10 保证 8 长连接 + 2 短连接余量，overflow=3 应对瞬时峰值。
# pool_recycle=1800 让长连接每 30 分钟被动回收，防止 stale transaction 堆积。
POOL_SIZE = 10
MAX_OVERFLOW = 3
POOL_RECYCLE_S = 1800

engine = create_async_engine(settings.database_url,
    pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE_S,
    pool_pre_ping=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_log.info(f"PG pool={POOL_SIZE}+{MAX_OVERFLOW} recycle={POOL_RECYCLE_S}s")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
