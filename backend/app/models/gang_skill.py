from datetime import datetime
from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangSkill(Base):
    __tablename__ = "gang_skills"
    __table_args__ = (UniqueConstraint("gang_id", "skill_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gang_id: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_name: Mapped[str] = mapped_column(String(32), nullable=False)
    current_level: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
