"""add gang_challenge_books to daily_records

Revision ID: 4c1b86466cea
Revises: 75d5652a17af
Create Date: 2026-07-17 15:42:36
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4c1b86466cea'
down_revision: Union[str, Sequence[str], None] = '75d5652a17af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('daily_records', sa.Column('gang_challenge_books', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('daily_records', 'gang_challenge_books')
