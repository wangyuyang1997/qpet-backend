"""认证相关：登录/注册/会话"""
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=2, max_length=64, description="手机号/邮箱/用户名")
    password: str = Field(..., min_length=6, max_length=128)


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str  # admin | user
    account_ids: list[str] = []


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_\-一-龥]{2,30}$")
    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SessionInfo(BaseModel):
    user_id: int
    username: str
    role: str
    account_ids: list[str] = []
