"""博物馆交易功能 — 幂等 DDL 迁移，支持重复执行"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIGRATION_SQL = [
    text("ALTER TABLE player_museum ADD COLUMN IF NOT EXISTS tradeable_fragments INTEGER DEFAULT 0"),
    text("ALTER TABLE daily_records ADD COLUMN IF NOT EXISTS museum_trades INTEGER DEFAULT 0"),
    text("""CREATE TABLE IF NOT EXISTS museum_trade (
        id SERIAL PRIMARY KEY,
        initiator_id VARCHAR(64) NOT NULL,
        target_id VARCHAR(64) NOT NULL,
        offer_item_id VARCHAR(32) NOT NULL,
        offer_quantity INTEGER DEFAULT 0,
        want_item_id VARCHAR(32) NOT NULL,
        want_quantity INTEGER DEFAULT 0,
        unique_code VARCHAR(16) NOT NULL,
        status VARCHAR(16) DEFAULT 'pending',
        message TEXT DEFAULT '',
        game_trade_id INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )"""),
]


async def run_migration():
    from app.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine

    try:
        engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
        async with engine.begin() as conn:
            for sql in MIGRATION_SQL:
                try:
                    await conn.execute(sql)
                except Exception as e:
                    logger.warning(f"[migration] {e}")
        await engine.dispose()
        logger.info("[migration] museum trade DDL applied")
    except Exception as e:
        logger.warning(f"[migration] DB 迁移失败: {e}")
