"""通用响应模型 — 所有 API 统一使用 { success, data?, message? }"""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """标准 API 响应"""
    success: bool
    data: Optional[T] = None
    message: str = ""


class PaginatedData(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int


class SSEEvent(BaseModel):
    """SSE 事件"""
    type: str  # log_insert | log_update | connected | heartbeat
    data: dict[str, Any]
