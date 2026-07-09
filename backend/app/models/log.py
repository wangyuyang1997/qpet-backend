from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[str | None] = mapped_column(Text)
    account: Mapped[str] = mapped_column(String(12), default="")


class LogHistory(Base):
    __tablename__ = "logs_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[str | None] = mapped_column(Text)
    account: Mapped[str] = mapped_column(String(12), default="")
