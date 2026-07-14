"""add farm dig and land upgrade fields to daily_records

Revision ID: b7f3a2c1e908
Revises: d5187e9146dc
Create Date: 2026-07-14 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b7f3a2c1e908'
down_revision: Union[str, Sequence[str], None] = 'd5187e9146dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("daily_records", sa.Column("digs", sa.Integer(), server_default="0"))
    op.add_column("daily_records", sa.Column("land_upgrades", sa.Integer(), server_default="0"))
    op.add_column("daily_records", sa.Column("research_points_earned", sa.Integer(), server_default="0"))
    op.add_column("daily_records", sa.Column("research_points_spent", sa.Integer(), server_default="0"))


def downgrade() -> None:
    op.drop_column("daily_records", "research_points_spent")
    op.drop_column("daily_records", "research_points_earned")
    op.drop_column("daily_records", "land_upgrades")
    op.drop_column("daily_records", "digs")
