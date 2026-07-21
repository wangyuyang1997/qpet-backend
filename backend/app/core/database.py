"""PostgreSQL 异步连接"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# PG max_connections=20：异步池上限8 + 日志同步池2，留余量给脚本/其他库
engine = create_async_engine(settings.database_url, pool_size=6, max_overflow=2,
                             pool_pre_ping=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
