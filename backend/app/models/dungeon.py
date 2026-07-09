"""副本 v4.4 5 张新表"""
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, DateTime, UniqueConstraint, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class DungeonConfig(Base):
    __tablename__ = "dungeon_configs"
    __table_args__ = (UniqueConstraint("account_id", "dungeon_type", "difficulty"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"))
    dungeon_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(16), default="normal")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DungeonStrategy(Base):
    __tablename__ = "dungeon_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    dungeon_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(16), default="normal")
    use_revive: Mapped[bool] = mapped_column(Boolean, default=False)
    target_floor: Mapped[int] = mapped_column(Integer, default=0)
    auto_repeat: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DungeonTemplate(Base):
    __tablename__ = "dungeon_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    strategy_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DungeonHistory(Base):
    __tablename__ = "dungeon_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"))
    dungeon_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(16))
    floors_cleared: Mapped[int] = mapped_column(Integer, default=0)
    exp_gained: Mapped[int] = mapped_column(Integer, default=0)
    items_dropped: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DungeonSession(Base):
    __tablename__ = "dungeon_sessions"
    __table_args__ = (UniqueConstraint("account_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"))
    dungeon_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[str] = mapped_column(String(16))
    current_floor: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="idle")  # idle/running/paused/done
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
