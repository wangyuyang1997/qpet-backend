from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class PlayerCollection(Base):
    __tablename__ = "player_collection"
    __table_args__ = (UniqueConstraint("account_id", "crop_id", "quality"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    crop_id: Mapped[str] = mapped_column(String(32), nullable=False)
    quality: Mapped[str] = mapped_column(String(8), nullable=False)
    is_collected: Mapped[bool] = mapped_column(Boolean, default=False)
    first_harvested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
