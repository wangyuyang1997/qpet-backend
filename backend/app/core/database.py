"""PostgreSQL 异步连接 — 池大小自动适配 PG max_connections"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

_log = logging.getLogger("qpet.db")

# --reload 产生双进程（reloader + worker），各自独立建池。
# 自动按 PG 上限计算安全池大小：2 进程 × 池上限 < PG max_connections。
def _safe_pool(pg_max: int) -> tuple[int, int]:
    budget = max(1, pg_max - int(pg_max * 0.2))  # 留20%给脚本和管理连接
    per_process = budget // 2
    size = max(4, per_process * 3 // 4)
    overflow = per_process - size
    return size, overflow

try:
    import psycopg2
    conn = psycopg2.connect(
        host=settings.pg_host, port=settings.pg_port,
        user=settings.pg_user, password=settings.pg_password,
        database=settings.pg_database, connect_timeout=5,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SHOW max_connections")
    pg_max = int(cur.fetchone()[0])
    cur.close(); conn.close()
except Exception:
    pg_max = 50  # 已在服务器设为50，保守回退

pool_size, max_overflow = _safe_pool(pg_max)

engine = create_async_engine(settings.database_url,
    pool_size=pool_size, max_overflow=max_overflow,
    pool_pre_ping=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_log.info(f"PG max_connections={pg_max} → pool={pool_size}+{max_overflow} "
          f"(安全于 {'reloader' if pg_max >= 32 else '单进程'}模式)")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
