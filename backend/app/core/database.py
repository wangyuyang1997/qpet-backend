"""PostgreSQL 异步连接"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# PG max_connections=20：异步池上限16 + 日志同步池2，留余量给脚本/其他库
engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=6,
                             pool_pre_ping=True, pool_recycle=300, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
