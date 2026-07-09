from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user")
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(128))
    wechat_openid: Mapped[str | None] = mapped_column(String(128), unique=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(128))
    wechat_nickname: Mapped[str | None] = mapped_column(String(64))
    wechat_avatar: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "account_id"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(12), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
