"""配置服务 — 开关定义查询 + 账号配置读写"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.config_definition import ConfigDefinition
from app.models.account_config import AccountConfig
from app.core.redis import cache_get, cache_set

DEFS_CACHE_KEY = "qpet:config:definitions"
DEFS_CACHE_TTL = 600


class ConfigService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_definitions(self) -> list[dict]:
        cached = await cache_get(DEFS_CACHE_KEY)
        if cached:
            return json.loads(cached)
        result = await self.db.execute(select(ConfigDefinition).order_by(ConfigDefinition.category, ConfigDefinition.key))
        rows = result.scalars().all()
        data = [
            {
                "key": r.key,
                "value_type": r.value_type,
                "default_value": r.default_value,
                "description": r.description,
                "category": r.category,
            }
            for r in rows
        ]
        await cache_set(DEFS_CACHE_KEY, json.dumps(data), DEFS_CACHE_TTL)
        return data

    async def get_account_config(self, account_id: str) -> list[dict]:
        """返回该账号的有效配置 = 定义默认值 + 用户覆盖"""
        defs = await self.get_definitions()
        result = await self.db.execute(
            select(AccountConfig).where(AccountConfig.account_id == account_id)
        )
        overrides = {r.config_key: r.value for r in result.scalars().all()}

        out = []
        for d in defs:
            key = d["key"]
            out.append({
                "key": key,
                "value": overrides.get(key, d["default_value"]),
                "value_type": d["value_type"],
                "default_value": d["default_value"],
                "description": d["description"],
            })
        return out

    async def set_account_config(self, account_id: str, key: str, value: str) -> bool:
        """写入账号配置覆盖"""
        result = await self.db.execute(
            select(AccountConfig).where(
                AccountConfig.account_id == account_id,
                AccountConfig.config_key == key,
            )
        )
        row = result.scalar_one_or_none()
        try:
            if row:
                row.value = value
            else:
                row = AccountConfig(account_id=account_id, config_key=key, value=value)
                self.db.add(row)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return True

    async def get_value(self, account_id: str, key: str) -> str | None:
        """获取单个配置值（合并默认值）"""
        result = await self.db.execute(
            select(AccountConfig).where(
                AccountConfig.account_id == account_id,
                AccountConfig.config_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            return row.value

        def_result = await self.db.execute(
            select(ConfigDefinition).where(ConfigDefinition.key == key)
        )
        d = def_result.scalar_one_or_none()
        return d.default_value if d else None

    async def get_bool(self, account_id: str, key: str) -> bool:
        val = await self.get_value(account_id, key)
        return val and val.lower() in ("true", "1", "yes")
