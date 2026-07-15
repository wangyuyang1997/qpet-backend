"""账号数据 API — 透传游戏 API 原始数据给 Dashboard 前端"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.services.account_manager import list_accounts as get_all_accounts
from app.services.engine import get_engine, get_or_create_engine
from app.models.user import User, UserAccount

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    accounts = await get_all_accounts(db)

    # Filter by user: admin sees all, regular users see only their bound accounts
    role = user.get("role") or user.get("role")
    if user and role != "admin":
        user_id = user.get("user_id") or user.get("userId")
        account_ids = user.get("account_ids") or user.get("accountIds") or []
        bound_ids = set(account_ids)
        if user_id:
            result = await db.execute(
                select(UserAccount.account_id).where(UserAccount.user_id == user_id)
            )
            bound_ids |= {row[0] for row in result.fetchall()}
        accounts = [a for a in accounts if a["id"] in bound_ids]

    return {"success": True, "data": accounts}


@router.get("/{account_id}/farm")
async def get_account_farm(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine.farm_status:
        return {"success": False, "message": "引擎未运行"}

    status = await engine.farm_status.get()
    if not status:
        return {"success": False, "message": "获取农场状态失败"}

    return {"success": True, "data": status}


@router.get("/{account_id}/character")
async def get_account_character(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine.client:
        return {"success": False, "message": "引擎未运行"}

    result = await engine.client.get_character()
    if result.get("success"):
        return {"success": True, "data": result.get("data", result)}
    return {"success": False, "message": result.get("message", "获取角色失败")}


@router.get("/{account_id}/sso-data")
async def get_account_sso(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine.client:
        return {"success": False, "message": "引擎未运行"}

    return {"success": True, "data": {
        "token": engine.client.token or "",
        "jwk": engine.client._ecdsa_jwk or {},
    }}


@router.post("/{account_id}/start")
async def start_account(account_id: str, _user: dict = Depends(get_current_user)):
    engine = await get_or_create_engine(account_id)
    if not engine:
        return {"success": False, "message": "账号不存在"}
    if engine._running:
        return {"success": True, "message": "已在运行中"}
    ok = await engine.start()
    if not ok:
        return {"success": False, "message": "引擎启动失败，请检查账号凭证是否有效"}
    return {"success": True, "message": "引擎已启动"}


@router.post("/{account_id}/stop")
async def stop_account(account_id: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine or not engine._running:
        return {"success": False, "message": "引擎未运行"}
    await engine.stop()
    return {"success": True, "message": "引擎已停止"}


@router.post("/{account_id}/{action}")
async def trigger_action(account_id: str, action: str, _user: dict = Depends(get_current_user)):
    engine = get_engine(account_id)
    if not engine:
        return {"success": False, "message": "引擎不存在"}
    if not engine._running:
        return {"success": False, "message": "引擎未运行"}

    if action == "cycle":
        await engine.full_cycle()
    elif action == "fight":
        await engine._run_battle()
    elif action == "farm":
        await engine._run_farm()
    elif action == "checkin":
        await engine.checkin.run()
    else:
        return {"success": False, "message": f"未知操作: {action}"}

    return {"success": True, "message": f"{action} 已触发"}
