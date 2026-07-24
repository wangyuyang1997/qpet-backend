from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangStatus(Base):
    __tablename__ = "gang_status"

    gang_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
    notice: Mapped[str] = mapped_column(Text, default="")
    accumulated_contribution: Mapped[int] = mapped_column(Integer, default=0)
    contribution: Mapped[int] = mapped_column(Integer, default=0)  # 当前可用的帮派共享贡献
    guardian_level: Mapped[int] = mapped_column(Integer, default=0)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    next_level: Mapped[int] = mapped_column(Integer, default=0)
    next_need_contrib: Mapped[int] = mapped_column(Integer, default=0)
    next_member_limit: Mapped[int] = mapped_column(Integer, default=0)
    level_progress: Mapped[int] = mapped_column(Integer, default=0)
    avatar: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
