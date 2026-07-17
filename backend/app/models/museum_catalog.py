from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class MuseumCatalog(Base):
    __tablename__ = "museum_catalog"

    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    rarity: Mapped[str] = mapped_column(String(8), nullable=False)
    fragments_needed: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
