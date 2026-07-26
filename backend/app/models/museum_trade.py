from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class MuseumTrade(Base):
    __tablename__ = "museum_trade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    offer_item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    offer_quantity: Mapped[int] = mapped_column(Integer, default=0)
    want_item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    want_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unique_code: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / accepted / rejected
    message: Mapped[str] = mapped_column(Text, default="")
    game_trade_id: Mapped[int] = mapped_column(Integer, default=0)  # 主站 trade ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
