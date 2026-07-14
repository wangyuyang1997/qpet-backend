"""账号数据 API: GET /api/accounts, /api/accounts/:id/farm, /character"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.services.account_manager import AccountManager
from app.services.engine import get_engine
from app.schemas.account import FarmDetail, CharacterDetail
from app.schemas.common import APIResponse

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    mgr = AccountManager(db)
    accounts = await mgr.list_accounts()
    return {"success": True, "data": accounts}


@router.get("/{account_id}/farm", response_model=APIResponse[FarmDetail])
async def get_account_farm(
    account_id: str,
    _user: dict = Depends(get_current_user),
):
    engine = get_engine(account_id)
    if not engine or not engine.farm_status:
        return APIResponse(success=False, message="引擎未运行或无农场数据")

    status = await engine.farm_status.get()
    if not status:
        return APIResponse(success=False, message="获取农场状态失败")

    return APIResponse(
        success=True,
        data=FarmDetail(
            unlocked_slots=status.get("unlockedSlots", 0),
            slots=status.get("slots", []),
            is_premium=status.get("isPremium", False),
            vip_slot_index=status.get("vipSlotIndex", -1),
            collection=status.get("collection", []),
            crop_config=status.get("cropConfig", []),
            daily_tasks=status.get("dailyTasksWithProgress", []),
            today_harvest_exp=status.get("todayHarvestExp", 0),
            experience=status.get("experience", 0),
            level=status.get("level", 0),
            museum=status.get("museum", {}),
            exploration_status=status.get("explorationStatus", {}),
            land_levels=status.get("landLevels", []),
            pet_guard_info=status.get("petGuardInfo"),
        ),
    )


@router.get("/{account_id}/character", response_model=APIResponse[CharacterDetail])
async def get_account_character(
    account_id: str,
    _user: dict = Depends(get_current_user),
):
    engine = get_engine(account_id)
    if not engine:
        return APIResponse(success=False, message="引擎未运行")

    char = engine._character_cache or {}
    return APIResponse(
        success=True,
        data=CharacterDetail(
            nickname=char.get("nickname", ""),
            level=char.get("level", 0),
            class_name=char.get("className", ""),
            combat_power=char.get("combatPower", 0),
            pvp_stats=char.get("pvpStats", {}),
            skills=char.get("skills", []),
            weapons=char.get("weapons", []),
            equipment=char.get("equipment", []),
        ),
    )
