"""AI 助手 API — POST /api/ai/chat SSE 流式对话"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.core.redis import cache_get
from app.core.crypto import load_key_store, import_private_key
from app.models.ai_conversation import AIConversation
from app.services.ai import service
from app.services.ai.tools import run_tools
from app.services.qpet_client import QPetClient
from app.models.account import Account
from sqlalchemy import select

logger = logging.getLogger("qpet.ai")

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AIChatRequest(BaseModel):
    message: str
    accountId: str = ""
    history: Optional[list[dict]] = None


@router.post("/chat")
async def ai_chat(
    req: AIChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式 AI 对话"""
    if not service.is_ready:
        return {"success": False, "message": "AI 未配置"}

    account_id = req.accountId
    user_id = user.get("user_id") or user.get("userId", 0)
    username = user.get("username", "")

    # 1. 获取角色数据
    char_data = {}
    qpet_client = None
    if account_id:
        # 从 Redis 读取角色缓存
        cached = await cache_get(f"qpet:{account_id}:character")
        if cached:
            try:
                char_data = json.loads(cached)
            except Exception:
                pass

        # 创建 QPetClient 以查询工具数据
        qpet_client = None
        r = await db.execute(select(Account).where(Account.id == account_id))
        acc = r.scalar_one_or_none()
        if acc:
            qpet_client = QPetClient(acc.id, acc.token)
            store = load_key_store()
            jwk = store.get(acc.id)
            if jwk:
                try:
                    qpet_client.private_key = import_private_key(jwk)
                    qpet_client._ready = True
                except Exception:
                    pass

    # 2. 预取工具数据
    tool_results = []
    if qpet_client:
        try:
            tool_results = await run_tools(req.message, qpet_client)
        except Exception as e:
            logger.debug(f"工具查询失败: {e}")

    # 3. 日志回调（独立 DB 会话，不受 StreamingResponse 生命周期影响）
    async def write_log(entry: dict):
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as log_db:
            try:
                conv = AIConversation(
                    user_id=entry["user_id"],
                    username=entry["username"],
                    account_id=entry.get("account_id", ""),
                    question=entry["question"],
                    answer=entry.get("answer", ""),
                    model=entry.get("model", "deepseek-v4-pro"),
                    is_core_related=entry.get("is_core_related", 0),
                    is_dangerous=entry.get("is_dangerous", 0),
                    is_strategy_matched=entry.get("is_strategy_matched", 0),
                    satisfied=entry.get("satisfied", 0),
                    tools_used=entry.get("tools_used"),
                    tools_data_size=entry.get("tools_data_size", 0),
                    prompt_tokens=entry.get("prompt_tokens", 0),
                    completion_tokens=entry.get("completion_tokens", 0),
                    elapsed_ms=entry.get("elapsed_ms", 0),
                    from_cache=entry.get("from_cache", False),
                    tags=entry.get("tags"),
                )
                log_db.add(conv)
                await log_db.commit()
            except Exception as e:
                logger.debug(f"AI 日志写入失败: {e}")

    # 4. 流式返回 — 前端直接拼 content，不需要 SSE 包装
    async def event_generator():
        try:
            async for event in service.chat(
                req.message,
                account_id=account_id,
                char_data=char_data,
                history=req.history,
                tool_results=tool_results,
                user_id=user_id,
                username=username,
                log_callback=write_log,
            ):
                if "chunk" in event:
                    yield event["chunk"]
                elif "cached" in event:
                    yield event["content"]
                elif "error" in event:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
