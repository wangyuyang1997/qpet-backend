from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class PlayerMuseum(Base):
    __tablename__ = "player_museum"
    __table_args__ = (UniqueConstraint("account_id", "item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    fragment_count: Mapped[int] = mapped_column(Integer, default=0)
    tradeable_fragments: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(4), default="见")
    is_repaired: Mapped[bool] = mapped_column(Boolean, default=False)
    repaired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
