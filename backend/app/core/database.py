"""PostgreSQL 异步连接"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# PG max_connections=20，8引擎+API请求，单进程池上限6（reloader双进程×6=12，留8余量）
engine = create_async_engine(settings.database_url, pool_size=4, max_overflow=2,
                             pool_pre_ping=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
