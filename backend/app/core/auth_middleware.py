"""认证中间件 — FastAPI 依赖注入"""
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.core.redis import session_get, session_extend


async def get_token_from_request(request: Request) -> Optional[str]:
    """从 Authorization header 或 ?_t= 参数提取 token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.query_params.get("_t")


async def get_current_user(request: Request) -> dict:
    """authMiddleware — 必须登录"""
    token = await get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    session = await session_get(token)
    if not session:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    await session_extend(token)
    return session


async def get_optional_user(request: Request) -> Optional[dict]:
    """authSoft — 可选登录，不阻断"""
    token = await get_token_from_request(request)
    if not token:
        return None

    session = await session_get(token)
    if session:
        await session_extend(token)
    return session


def require_role(*roles: str):
    """角色校验依赖工厂"""
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return checker
