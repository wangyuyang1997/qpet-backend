"""配置管理 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth_middleware import get_current_user
from app.services.config_service import ConfigService
from app.schemas.config import ConfigUpdateRequest

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/definitions")
async def list_definitions(db: AsyncSession = Depends(get_db), _user: dict = Depends(get_current_user)):
    svc = ConfigService(db)
    return {"success": True, "data": await svc.get_definitions()}


@router.get("")
async def get_account_config(
    account: str = Query(..., description="账号ID"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ConfigService(db)
    return {"success": True, "data": await svc.get_account_config(account)}


@router.put("")
async def update_config(
    body: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ConfigService(db)
    await svc.set_account_config(body.account_id, body.key, body.value)
    return {"success": True}
