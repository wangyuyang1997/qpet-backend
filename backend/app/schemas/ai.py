"""AI 对话 schema"""
from pydantic import BaseModel, Field
from typing import Optional


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    account_id: Optional[str] = None
    history: list[dict] = []  # [{role: "user"|"assistant", content: str}]
