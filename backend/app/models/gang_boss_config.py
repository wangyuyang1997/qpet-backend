from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class GangBossConfig(Base):
    __tablename__ = "gang_boss_configs"

    boss_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    boss_level: Mapped[int] = mapped_column(Integer, default=0)
    min_gang_level: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
