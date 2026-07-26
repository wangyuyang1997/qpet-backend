"""add museum trade features: tradeable_fragments, museum_trades, museum_trade table

Revision ID: 7a8b9c0d1e2f
Revises: 6f1a2b3c4d5e
Create Date: 2026-07-26 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '6f1a2b3c4d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # player_museum 加可交易碎片数
    op.add_column("player_museum", sa.Column("tradeable_fragments", sa.Integer(), server_default="0"))

    # daily_records 加博物馆交易次数
    op.add_column("daily_records", sa.Column("museum_trades", sa.Integer(), server_default="0"))

    # 新建 museum_trade 表
    op.create_table(
        "museum_trade",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("initiator_id", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("offer_item_id", sa.String(32), nullable=False),
        sa.Column("offer_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("want_item_id", sa.String(32), nullable=False),
        sa.Column("want_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_code", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), default=""),
        sa.Column("game_trade_id", sa.Integer(), default=0),  # 主站 trade ID
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("museum_trade")
    op.drop_column("daily_records", "museum_trades")
    op.drop_column("player_museum", "tradeable_fragments")
