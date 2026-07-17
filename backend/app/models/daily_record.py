from datetime import datetime
from sqlalchemy import String, Integer, Date, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class DailyRecord(Base):
    __tablename__ = "daily_records"
    __table_args__ = (UniqueConstraint("account_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0)
    class_name: Mapped[str] = mapped_column(String(32), default="")
    combat_power: Mapped[int] = mapped_column(Integer, default=0)
    npc_fights: Mapped[int] = mapped_column(Integer, default=0)
    tower_floors: Mapped[int] = mapped_column(Integer, default=0)
    tower_max: Mapped[int] = mapped_column(Integer, default=0)
    harvests: Mapped[int] = mapped_column(Integer, default=0)
    plants: Mapped[int] = mapped_column(Integer, default=0)
    steals: Mapped[int] = mapped_column(Integer, default=0)
    waters: Mapped[int] = mapped_column(Integer, default=0)
    help_waters: Mapped[int] = mapped_column(Integer, default=0)
    digs: Mapped[int] = mapped_column(Integer, default=0)
    land_upgrades: Mapped[int] = mapped_column(Integer, default=0)
    research_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    research_points_spent: Mapped[int] = mapped_column(Integer, default=0)
    farm_ads: Mapped[int] = mapped_column(Integer, default=0)
    stamina_ads: Mapped[int] = mapped_column(Integer, default=0)
    community_ads: Mapped[int] = mapped_column(Integer, default=0)
    diversity: Mapped[int] = mapped_column(Integer, default=0)
    coll_crops: Mapped[int] = mapped_column(Integer, default=0)
    coll_slots: Mapped[int] = mapped_column(Integer, default=0)
    exp_visit: Mapped[int] = mapped_column(Integer, default=0)
    current_exp: Mapped[int] = mapped_column(Integer, default=0)
    exp_battle: Mapped[int] = mapped_column(Integer, default=0)
    today_harvest_exp: Mapped[int] = mapped_column(Integer, default=0)
    stamina: Mapped[int] = mapped_column(Integer, default=0)
    max_stamina: Mapped[int] = mapped_column(Integer, default=0)
    level_exp: Mapped[int] = mapped_column(Integer, default=0)
    level_exp_max: Mapped[int] = mapped_column(Integer, default=0)
    gang_contribution: Mapped[int] = mapped_column(Integer, default=0)
    abyss_tickets: Mapped[int] = mapped_column(Integer, default=0)
    challenge_books: Mapped[int] = mapped_column(Integer, default=0)
    flowers_sent: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
