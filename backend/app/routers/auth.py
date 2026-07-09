"""认证路由: POST /api/auth/login, logout, register; GET /api/auth/me"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password, verify_password, is_legacy_hash, generate_session_token, create_jwt
from app.core.redis import session_set, session_delete
from app.core.auth_middleware import get_current_user, get_optional_user
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, SessionInfo
from app.schemas.common import APIResponse
from app.models.user import User, UserAccount

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=APIResponse[LoginResponse])
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 手机号/邮箱/用户名 三路查找
    result = await db.execute(
        select(User).where(
            (User.phone == req.login) | (User.email == req.login) | (User.username == req.login)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return APIResponse(success=False, message="账号不存在")

    if not verify_password(req.password, user.password_hash):
        return APIResponse(success=False, message="密码错误")

    # SHA256 遗留 → bcrypt 自动升级
    if is_legacy_hash(user.password_hash):
        user.password_hash = hash_password(req.password)
        await db.commit()

    # 查绑定的账号 ID 列表
    acct_result = await db.execute(
        select(UserAccount.account_id).where(UserAccount.user_id == user.id)
    )
    account_ids = [row[0] for row in acct_result.fetchall()]

    # 生成 session token 存入 Redis
    token = generate_session_token()
    sess_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "account_ids": account_ids,
    }
    await session_set(token, sess_data)

    return APIResponse(
        success=True,
        data=LoginResponse(
            token=token,
            user_id=user.id,
            username=user.username,
            role=user.role,
            account_ids=account_ids,
        ),
    )


@router.post("/logout", response_model=APIResponse)
async def logout(user: dict = Depends(get_optional_user)):
    if user:
        token = user.get("_token")
        if token:
            await session_delete(token)
    return APIResponse(success=True)


@router.get("/me", response_model=APIResponse[SessionInfo])
async def me(user: dict = Depends(get_optional_user)):
    if not user:
        return APIResponse(success=False, message="未登录")
    return APIResponse(
        success=True,
        data=SessionInfo(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            account_ids=user.get("account_ids", []),
        ),
    )


@router.post("/register", response_model=APIResponse[dict])
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        return APIResponse(success=False, message="用户名已存在")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role="user",
        phone=req.phone,
        email=req.email,
    )
    db.add(user)
    await db.commit()

    return APIResponse(success=True, data={"id": user.id, "username": user.username})
