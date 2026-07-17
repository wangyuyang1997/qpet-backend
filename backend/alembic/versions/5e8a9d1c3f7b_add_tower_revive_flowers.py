"""add tower_revive and flowers_remaining to daily_records

Revision ID: 5e8a9d1c3f7b
Revises: 4c1b86466cea
Create Date: 2026-07-17 16:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '5e8a9d1c3f7b'
down_revision: Union[str, Sequence[str], None] = '4c1b86466cea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('daily_records', sa.Column('tower_revive', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('daily_records', sa.Column('flowers_remaining', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('daily_records', 'flowers_remaining')
    op.drop_column('daily_records', 'tower_revive')
