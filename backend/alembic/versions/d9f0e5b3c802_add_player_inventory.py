"""add player_inventory table

Revision ID: d9f0e5b3c802
Revises: c8e9f4d2a701
Create Date: 2026-07-16 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd9f0e5b3c802'
down_revision: Union[str, Sequence[str], None] = 'c8e9f4d2a701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_inventory",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(64), server_default=""),
        sa.Column("item_type", sa.String(16), server_default=""),
        sa.Column("game_item_id", sa.String(64), server_default=""),
        sa.Column("quantity", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("player_inventory")
