"""add_config_definitions_and_account_configs

Revision ID: d5187e9146dc
Revises:
Create Date: 2026-07-09 16:44:32.423456

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd5187e9146dc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "config_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value_type", sa.String(16), server_default="bool"),
        sa.Column("default_value", sa.Text(), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("category", sa.String(32), server_default="general"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "account_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(12), nullable=False),
        sa.Column("config_key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "config_key", name="uq_account_config"),
    )
    # 种子数据
    op.execute("""
        INSERT INTO config_definitions (key, value_type, default_value, description, category) VALUES
        ('tower_use_revive',         'bool', 'true',  '爬塔无免费次数时是否使用还魂丹', 'battle'),
        ('exp_boost_enabled',        'bool', 'true',  '经验药水不足时自动从背包补充', 'buff'),
        ('supply_revive',            'bool', 'true',  '还魂丹不足时自动从背包补充', 'supply'),
        ('supply_challenge_book',    'bool', 'true',  '帮派挑战书不足时自动从背包补充', 'supply'),
        ('supply_flowers',           'bool', 'true',  '鲜花不足时自动从背包补充', 'supply'),
        ('supply_beads',             'bool', 'false', '魂珠不足时自动从背包补充', 'supply'),
        ('auto_checkin',             'bool', 'true',  '自动签到', 'daily'),
        ('auto_chest',               'bool', 'true',  '自动开典藏宝箱', 'daily'),
        ('auto_ad_stamina',          'bool', 'true',  '自动领取广告体力', 'ad'),
        ('auto_ad_farm',             'bool', 'true',  '自动领取农场广告', 'ad'),
        ('auto_ad_community',        'bool', 'true',  '自动领取社区广告', 'ad'),
        ('auto_shop_stamina',        'bool', 'true',  '自动购买体力道具', 'shop'),
        ('auto_shop_challenge_book', 'bool', 'true',  '自动购买帮派挑战书', 'shop'),
        ('auto_npc_fight',           'bool', 'true',  '自动NPC乐斗', 'battle'),
        ('auto_tower',               'bool', 'true',  '自动爬塔', 'battle'),
        ('auto_gang_boss',           'bool', 'true',  '自动帮派BOSS', 'battle'),
        ('auto_world_boss',          'bool', 'true',  '自动世界BOSS', 'battle'),
        ('auto_tournament',          'bool', 'true',  '自动报名赛事', 'battle'),
        ('auto_class_upgrade',       'bool', 'true',  '自动职业技能分配', 'role'),
        ('auto_upgrade',             'bool', 'true',  '自动魂珠合成', 'role'),
        ('auto_equip',               'bool', 'true',  '自动装备替换', 'role'),
        ('auto_marriage_boss',       'bool', 'true',  '自动夫妻BOSS', 'social'),
        ('auto_marriage_gift',       'bool', 'true',  '自动婚内送花', 'social'),
        ('auto_marriage_flowers',    'bool', 'true',  '自动好友送花(未婚)', 'social'),
        ('auto_marriage_proposal',   'bool', 'true',  '自动求婚/接受求婚', 'social'),
        ('auto_friend_sync',         'bool', 'true',  '自动好友同步', 'social'),
        ('auto_gang_donate',         'bool', 'true',  '自动帮派捐赠', 'social')
    """)


def downgrade() -> None:
    op.drop_table("account_configs")
    op.drop_table("config_definitions")
