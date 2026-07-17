from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class CollectionCatalog(Base):
    __tablename__ = "collection_catalog"

    crop_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    crop_name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    crop_rarity: Mapped[str] = mapped_column(String(8), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
