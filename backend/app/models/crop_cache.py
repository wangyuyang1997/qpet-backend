from datetime import datetime
from sqlalchemy import String, Integer, Double, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class CropCache(Base):
    __tablename__ = "crop_cache"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    category: Mapped[str] = mapped_column(String(32), default="")
    rarity: Mapped[str] = mapped_column(String(16), default="normal")
    growth_minutes: Mapped[int] = mapped_column(Integer, default=0)
    level_required: Mapped[int] = mapped_column(Integer, default=1)
    exp_reward: Mapped[int] = mapped_column(Integer, default=0)
    seed_cost: Mapped[int] = mapped_column(Integer, default=0)
    profit: Mapped[int] = mapped_column(Integer, default=0)
    ppm: Mapped[float] = mapped_column(Double, default=0.0)
    double_cost: Mapped[int] = mapped_column(Integer, default=0)
    double_profit: Mapped[int] = mapped_column(Integer, default=0)
    double_ppm: Mapped[float] = mapped_column(Double, default=0.0)
    is_vip: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
