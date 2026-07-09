from datetime import datetime, date
from sqlalchemy import String, Integer, Text, Boolean, SmallInteger, Numeric, Date, DateTime, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(64), default="")
    account_id: Mapped[str | None] = mapped_column(String(12))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(32), default="deepseek-v4-pro")
    is_core_related: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_dangerous: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_strategy_matched: Mapped[int] = mapped_column(SmallInteger, default=0)
    satisfied: Mapped[int] = mapped_column(SmallInteger, default=0)
    tools_used: Mapped[str | None] = mapped_column(Text)
    tools_data_size: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIDailySummary(Base):
    __tablename__ = "ai_daily_summary"
    __table_args__ = (UniqueConstraint("date", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(64), default="")
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0)
    core_related_count: Mapped[int] = mapped_column(Integer, default=0)
    core_related_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    dangerous_count: Mapped[int] = mapped_column(Integer, default=0)
    strategy_matched_count: Mapped[int] = mapped_column(Integer, default=0)
    strategy_matched_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    satisfied_count: Mapped[int] = mapped_column(Integer, default=0)
    satisfied_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    tools_total_calls: Mapped[int] = mapped_column(Integer, default=0)
    tools_top: Mapped[str | None] = mapped_column(Text)
    top_tags: Mapped[str | None] = mapped_column(Text)
    sample_questions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
