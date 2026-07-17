"""add gang tables: gang_status, gang_skill_configs, gang_boss_configs, gang_skills, gang_bosses, gang_members

Revision ID: 6f1a2b3c4d5e
Revises: 5e8a9d1c3f7b
Create Date: 2026-07-17 17:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6f1a2b3c4d5e'
down_revision: Union[str, Sequence[str], None] = '5e8a9d1c3f7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # gang_skill_configs
    op.create_table('gang_skill_configs',
        sa.Column('name', sa.String(32), primary_key=True),
        sa.Column('description', sa.String(64), server_default=''),
        sa.Column('max_level', sa.Integer(), server_default='20'),
        sa.Column('cost_per_level', sa.Integer(), server_default='0'),
        sa.Column('min_gang_level', sa.Integer(), server_default='1'),
        sa.Column('hp_per_level', sa.Integer(), server_default='0'),
        sa.Column('atk_per_level', sa.Integer(), server_default='0'),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
    )

    # gang_boss_configs
    op.create_table('gang_boss_configs',
        sa.Column('boss_id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(32), nullable=False),
        sa.Column('boss_level', sa.Integer(), server_default='0'),
        sa.Column('min_gang_level', sa.Integer(), server_default='1'),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
    )

    # gang_status
    op.create_table('gang_status',
        sa.Column('gang_id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('level', sa.Integer(), server_default='1'),
        sa.Column('notice', sa.Text(), server_default=''),
        sa.Column('accumulated_contribution', sa.Integer(), server_default='0'),
        sa.Column('guardian_level', sa.Integer(), server_default='0'),
        sa.Column('member_count', sa.Integer(), server_default='0'),
        sa.Column('next_level', sa.Integer(), server_default='0'),
        sa.Column('next_need_contrib', sa.Integer(), server_default='0'),
        sa.Column('next_member_limit', sa.Integer(), server_default='0'),
        sa.Column('level_progress', sa.Integer(), server_default='0'),
        sa.Column('avatar', sa.String(256), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # gang_skills
    op.create_table('gang_skills',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('gang_id', sa.Integer(), nullable=False),
        sa.Column('skill_name', sa.String(32), nullable=False),
        sa.Column('current_level', sa.Integer(), server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('gang_id', 'skill_name'),
    )

    # gang_bosses
    op.create_table('gang_bosses',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('gang_id', sa.Integer(), nullable=False),
        sa.Column('boss_id', sa.Integer(), nullable=False),
        sa.Column('unlocked', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('free_challenge_done', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('gang_id', 'boss_id'),
    )

    # gang_members
    op.create_table('gang_members',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('gang_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(12), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('nickname', sa.String(64), server_default=''),
        sa.Column('role', sa.String(16), server_default='member'),
        sa.Column('contribution', sa.Integer(), server_default='0'),
        sa.Column('joined_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('gang_id', 'user_id'),
    )


def downgrade() -> None:
    op.drop_table('gang_members')
    op.drop_table('gang_bosses')
    op.drop_table('gang_skills')
    op.drop_table('gang_status')
    op.drop_table('gang_boss_configs')
    op.drop_table('gang_skill_configs')
