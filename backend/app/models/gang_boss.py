from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangBoss(Base):
    __tablename__ = "gang_bosses"
    __table_args__ = (UniqueConstraint("gang_id", "boss_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gang_id: Mapped[int] = mapped_column(Integer, nullable=False)
    boss_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    free_challenge_done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
