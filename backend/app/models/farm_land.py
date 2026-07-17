from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class FarmLand(Base):
    __tablename__ = "farm_land"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    land_level: Mapped[int] = mapped_column(Integer, default=1)
    land_name: Mapped[str] = mapped_column(String(16), default="普通土地")
    research_points: Mapped[int] = mapped_column(Integer, default=0)
    next_level: Mapped[int] = mapped_column(Integer, default=2)
    next_name: Mapped[str] = mapped_column(String(16), default="肥沃土地")
    next_rp_needed: Mapped[int] = mapped_column(Integer, default=200)
    next_artifacts: Mapped[int] = mapped_column(Integer, default=4)
    next_growth_pct: Mapped[int] = mapped_column(Integer, default=-2)
    next_harvest_pct: Mapped[int] = mapped_column(Integer, default=2)
    can_upgrade: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
