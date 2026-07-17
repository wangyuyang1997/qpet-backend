from datetime import datetime
from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangMember(Base):
    __tablename__ = "gang_members"
    __table_args__ = (UniqueConstraint("gang_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gang_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="member")
    contribution: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
