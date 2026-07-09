from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    level: Mapped[int] = mapped_column(Integer, default=0)
    class_name: Mapped[str] = mapped_column(String(32), default="")
    token: Mapped[str] = mapped_column(Text, default="")
    running: Mapped[int] = mapped_column(Integer, default=0)
    automation: Mapped[dict] = mapped_column(JSONB, default=dict)
    username: Mapped[str] = mapped_column(String(64), default="")
    password: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    is_premium: Mapped[int] = mapped_column(Integer, default=0)
    premium_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
