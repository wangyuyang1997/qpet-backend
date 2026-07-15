"""Redis 连接 + session/限流/锁/缓存。Redis 不可用时 session 退化为内存存储。"""
import json
import logging
import time
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("qpet.redis")
_client: Optional[aioredis.Redis] = None

# 内存兜底：Redis 不可用时用 dict 存储 session（开发/单机环境）
_mem_sessions: dict[str, dict] = {}
_mem_ttl: dict[str, float] = {}


def _redis_ok() -> bool:
    return _client is not None


async def init_redis():
    global _client
    try:
        _client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        await _client.ping()
        print(f"[redis] 连接成功: {settings.redis_host}:{settings.redis_port}")
        logger.info(f"Redis 连接成功: {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        _client = None
        print(f"[redis] 连接失败: {e}")
        logger.warning(f"Redis 不可用 ({e})，session 退化为内存存储（重启丢失，仅限开发环境）")


async def close_redis():
    if _client:
        await _client.close()


# ── Session ──

async def session_get(token: str) -> Optional[dict]:
    if _redis_ok():
        data = await _client.get(f"session:{token}")
        return json.loads(data) if data else None
    # 内存兜底
    entry = _mem_sessions.get(token)
    if entry and _mem_ttl.get(token, 0) > time.time():
        return entry
    if entry:
        del _mem_sessions[token]
        del _mem_ttl[token]
    return None


async def session_set(token: str, data: dict, ttl_hours: int = 12):
    if _redis_ok():
        await _client.setex(f"session:{token}", ttl_hours * 3600, json.dumps(data))
        return
    _mem_sessions[token] = data
    _mem_ttl[token] = time.time() + ttl_hours * 3600


async def session_delete(token: str):
    if _redis_ok():
        await _client.delete(f"session:{token}")
        return
    _mem_sessions.pop(token, None)
    _mem_ttl.pop(token, None)


async def session_extend(token: str, ttl_hours: int = 12):
    if _redis_ok():
        await _client.expire(f"session:{token}", ttl_hours * 3600)
        return
    if token in _mem_sessions:
        _mem_ttl[token] = time.time() + ttl_hours * 3600


# ── Rate Limiter ──

async def rate_limit_hit(account_id: str, limit_type: str) -> int:
    if not _redis_ok(): return 0
    key = f"rate:{account_id}:{limit_type}"
    count = await _client.incr(key)
    if count == 1:
        await _client.expire(key, 900)
    return count


async def rate_limit_reset(account_id: str, limit_type: str):
    if not _redis_ok(): return
    await _client.delete(f"rate:{account_id}:{limit_type}")


# ── Mutex ──

async def acquire_lock(lock_name: str, ttl_seconds: int = 30) -> bool:
    if not _redis_ok(): return True
    return await _client.set(f"lock:{lock_name}", "1", nx=True, ex=ttl_seconds)


async def release_lock(lock_name: str):
    if not _redis_ok(): return
    await _client.delete(f"lock:{lock_name}")


# ── Cache ──

async def cache_get(key: str) -> Optional[str]:
    if not _redis_ok(): return None
    return await _client.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int = 3600):
    if not _redis_ok(): return
    await _client.setex(key, ttl_seconds, value)


async def cache_delete(key: str):
    if not _redis_ok(): return
    await _client.delete(key)
