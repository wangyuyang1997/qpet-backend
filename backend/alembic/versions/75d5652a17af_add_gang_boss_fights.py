"""add gang_boss_fights to daily_records

Revision ID: 75d5652a17af
Revises: d9f0e5b3c802
Create Date: 2026-07-17 14:54:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '75d5652a17af'
down_revision: Union[str, Sequence[str], None] = 'd9f0e5b3c802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('daily_records', sa.Column('gang_boss_fights', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('daily_records', 'gang_boss_fights')
