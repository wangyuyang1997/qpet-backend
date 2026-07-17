"""日志系统 — 入库 + 折叠 + SSE 推送，对齐旧 Node.js logger.js"""
import logging
import asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from app.config import settings

_logger = logging.getLogger("qpet.audit")

# 折叠缓存: key = f"{account}::{module}::{message}" → { id, count, first_ts }
_fold_cache: dict[str, dict] = {}
FOLD_WINDOW_S = 300  # 5 分钟


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 用同步 engine 避免事件循环 task 丢失
_sync_engine = None


def _get_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        _sync_engine = create_engine(settings.database_url_sync)
    return _sync_engine


def _insert_log(level: str, category: str, module: str, message: str,
                account: str, data: str | None = None) -> int | None:
    try:
        eng = _get_engine()
        with eng.connect() as c:
            row = c.execute(
                text("""INSERT INTO logs (timestamp, level, category, module, message, account, data)
                        VALUES (:ts, :level, :cat, :mod, :msg, :acct, :data)
                        RETURNING id"""),
                {"ts": _now(), "level": level, "cat": category or "", "mod": module,
                 "msg": message, "acct": account, "data": data or None},
            )
            c.commit()
            result = row.fetchone()
            return result[0] if result else None
    except Exception as e:
        _logger.error(f"日志入库失败: {e}")
        return None


def _update_log_message(log_id: int, new_msg: str):
    try:
        eng = _get_engine()
        with eng.connect() as c:
            c.execute(
                text("UPDATE logs SET message=:msg WHERE id=:id"),
                {"msg": new_msg, "id": log_id},
            )
            c.commit()
    except Exception:
        pass


async def _broadcast(event: dict):
    try:
        from app.core.rabbitmq import publish_sse_event, publish_log
        await publish_sse_event(event["type"], event)
        await publish_log(event)
    except Exception:
        pass


def log(level: str, category: str, module: str, message: str,
        account_id: str = "", data: str | None = None):
    """写日志入库，5分钟内同账号+模块+消息自动折叠"""
    account = account_id or ""

    # 折叠检查
    fold_key = f"{account}::{module}::{message}"
    cached = _fold_cache.get(fold_key)
    now = asyncio.get_event_loop().time() if _event_loop() else __import__("time").time()
    if cached and (now - cached["first_ts"]) < FOLD_WINDOW_S:
        cached["count"] += 1
        folded_msg = f"{message} (×{cached['count']})"
        _update_log_message(cached["id"], folded_msg)
        # SSE broadcast async
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_broadcast({
                "type": "log_update", "id": cached["id"],
                "timestamp": _now(), "level": level,
                "category": category or "", "module": module,
                "message": folded_msg, "account": account,
                "count": cached["count"],
            }))
        except RuntimeError:
            pass
        return

    # 定期清理折叠缓存
    if len(_fold_cache) > 50:
        cutoff = now - FOLD_WINDOW_S * 2
        for k in list(_fold_cache.keys()):
            if _fold_cache[k]["first_ts"] < cutoff:
                del _fold_cache[k]

    # 同步写 DB
    log_id = _insert_log(level, category, module, message, account, data)
    if log_id:
        _fold_cache[fold_key] = {"id": log_id, "count": 1, "first_ts": now}
        # SSE broadcast async
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_broadcast({
                "type": "log_insert", "id": log_id,
                "timestamp": _now(), "level": level,
                "category": category or "", "module": module,
                "message": message, "data": data, "account": account,
            }))
        except RuntimeError:
            pass


def _event_loop():
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ——— 便捷函数 ———

def info(category: str, module: str, message: str, account_id: str = "", data: str | None = None):
    log("INFO", category, module, message, account_id, data)


def warn(category: str, module: str, message: str, account_id: str = "", data: str | None = None):
    log("WARN", category, module, message, account_id, data)


def error(category: str, module: str, message: str, account_id: str = "", data: str | None = None):
    log("ERROR", category, module, message, account_id, data)


def action(category: str, module: str, message: str, account_id: str = ""):
    log("INFO", category, module, message, account_id, None)
