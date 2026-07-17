"""add museum, collection and unified land tables

Revision ID: c8e9f4d2a701
Revises: b7f3a2c1e908
Create Date: 2026-07-16 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c8e9f4d2a701'
down_revision: Union[str, Sequence[str], None] = 'b7f3a2c1e908'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "museum_catalog",
        sa.Column("item_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("rarity", sa.String(8), nullable=False),
        sa.Column("fragments_needed", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "collection_catalog",
        sa.Column("crop_id", sa.String(32), primary_key=True),
        sa.Column("crop_name", sa.String(64), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("crop_rarity", sa.String(8), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "player_museum",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("fragment_count", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(4), server_default="见"),
        sa.Column("is_repaired", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("repaired_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "item_id"),
    )

    op.create_table(
        "player_collection",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("crop_id", sa.String(32), nullable=False),
        sa.Column("quality", sa.String(8), nullable=False),
        sa.Column("is_collected", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("first_harvested_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "crop_id", "quality"),
    )

    op.create_table(
        "farm_land",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.String(64), unique=True, nullable=False),
        sa.Column("land_level", sa.Integer(), server_default="1"),
        sa.Column("land_name", sa.String(16), server_default="普通土地"),
        sa.Column("research_points", sa.Integer(), server_default="0"),
        sa.Column("next_level", sa.Integer(), server_default="2"),
        sa.Column("next_name", sa.String(16), server_default="肥沃土地"),
        sa.Column("next_rp_needed", sa.Integer(), server_default="200"),
        sa.Column("next_artifacts", sa.Integer(), server_default="4"),
        sa.Column("next_growth_pct", sa.Integer(), server_default="-2"),
        sa.Column("next_harvest_pct", sa.Integer(), server_default="2"),
        sa.Column("can_upgrade", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("farm_land")
    op.drop_table("player_collection")
    op.drop_table("player_museum")
    op.drop_table("collection_catalog")
    op.drop_table("museum_catalog")
