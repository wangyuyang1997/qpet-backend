from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangSkillConfig(Base):
    __tablename__ = "gang_skill_configs"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(String(64), default="")
    max_level: Mapped[int] = mapped_column(Integer, default=20)
    cost_per_level: Mapped[int] = mapped_column(Integer, default=0)
    min_gang_level: Mapped[int] = mapped_column(Integer, default=1)
    hp_per_level: Mapped[int] = mapped_column(Integer, default=0)
    atk_per_level: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
