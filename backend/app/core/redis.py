"""Redis 连接 + session/限流/锁/缓存"""
import json
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

_client: Optional[aioredis.Redis] = None


async def init_redis():
    global _client
    _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _client.ping()


async def close_redis():
    if _client:
        await _client.close()


# Session
async def session_get(token: str) -> Optional[dict]:
    data = await _client.get(f"session:{token}")
    return json.loads(data) if data else None


async def session_set(token: str, data: dict, ttl_hours: int = 12):
    await _client.setex(f"session:{token}", ttl_hours * 3600, json.dumps(data))


async def session_delete(token: str):
    await _client.delete(f"session:{token}")


async def session_extend(token: str, ttl_hours: int = 12):
    await _client.expire(f"session:{token}", ttl_hours * 3600)


# Rate Limiter
async def rate_limit_hit(account_id: str, limit_type: str) -> int:
    key = f"rate:{account_id}:{limit_type}"
    count = await _client.incr(key)
    if count == 1:
        await _client.expire(key, 900)  # 15min TTL
    return count


async def rate_limit_reset(account_id: str, limit_type: str):
    await _client.delete(f"rate:{account_id}:{limit_type}")


# Mutex
async def acquire_lock(lock_name: str, ttl_seconds: int = 30) -> bool:
    return await _client.set(f"lock:{lock_name}", "1", nx=True, ex=ttl_seconds)


async def release_lock(lock_name: str):
    await _client.delete(f"lock:{lock_name}")


# Cache
async def cache_get(key: str) -> Optional[str]:
    return await _client.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int = 3600):
    await _client.setex(key, ttl_seconds, value)


async def cache_delete(key: str):
    await _client.delete(key)
