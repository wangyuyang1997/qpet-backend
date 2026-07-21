"""预加载 API — 用户登录后一次性拉取全部绑定账号的核心数据"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.core.redis import cache_get
from app.models.account import Account
from app.models.user import UserAccount
from app.services.config_service import ConfigService
import json

router = APIRouter(prefix="/api/preload", tags=["preload"])


@router.get("")
async def preload(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """返回当前用户所有绑定账号的：基本信息 + 配置 + 角色缓存"""
    user_id = user.get("user_id") or user.get("userId")
    role = user.get("role", "")

    # 1. 获取绑定账号列表
    if role == "admin":
        r = await db.execute(select(Account.id))
        bound_ids = [row[0] for row in r.fetchall()]
    else:
        r = await db.execute(select(UserAccount.account_id).where(UserAccount.user_id == user_id))
        bound_ids = [row[0] for row in r.fetchall()]

    if not bound_ids:
        return {"success": True, "data": {}}

    # 2. 账号基本信息
    r = await db.execute(select(Account).where(Account.id.in_(bound_ids)))
    accounts = {}
    for row in r.scalars().all():
        accounts[row.id] = {
            "id": row.id,
            "name": row.nickname or row.id[:8],
            "level": row.level or 0,
            "class_name": row.class_name or "",
            "running": bool(row.running),
            "is_premium": bool(row.is_premium),
        }

    # 3. 配置（每个账号）
    svc = ConfigService(db)
    for aid in bound_ids:
        if aid in accounts:
            accounts[aid]["config"] = await svc.get_account_config(aid)

    # 4. 角色缓存（Redis，引擎已缓存的完整角色数据）
    for aid in bound_ids:
        if aid in accounts:
            try:
                char_cached = await cache_get(f"qpet:{aid}:character")
                if char_cached:
                    accounts[aid]["character"] = json.loads(char_cached)
            except Exception:
                pass

    # 5. 婚姻/农场/帮派缓存（Redis，引擎每循环预热）
    for aid in bound_ids:
        if aid in accounts:
            for key in ("marriage", "farm", "gang", "gang-boss"):
                try:
                    cached = await cache_get(f"qpet:{aid}:{key}")
                    if cached:
                        accounts[aid][key] = json.loads(cached)
                except Exception:
                    pass

    return {"success": True, "data": accounts}
