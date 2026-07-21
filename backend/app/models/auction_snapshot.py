from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class AuctionSnapshot(Base):
    __tablename__ = "auction_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    item_id: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    slot: Mapped[str] = mapped_column(String(32), default="")
    quality: Mapped[str] = mapped_column(String(16), default="")
    item_level: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(Integer, default=0)
    seller_name: Mapped[str] = mapped_column(String(64), default="")
    enhance_level: Mapped[int] = mapped_column(Integer, default=0)
    growth_level: Mapped[int] = mapped_column(Integer, default=0)
    class_required: Mapped[str] = mapped_column(String(64), default="")
    armor_type: Mapped[str] = mapped_column(String(32), default="")
    set_info: Mapped[str | None] = mapped_column(Text)
    base_stats: Mapped[str | None] = mapped_column(Text)
    affixes: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[str | None] = mapped_column(Text)
