from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class ChestRecord(Base):
    __tablename__ = "chest_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, default=0)
    drops: Mapped[dict] = mapped_column(JSONB, default=list)
    total_opens: Mapped[int] = mapped_column(Integer, default=0)
    date_key: Mapped[str] = mapped_column(String(10), default="")
