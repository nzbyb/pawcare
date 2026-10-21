"""add notification category, link and dedupe key

Revision ID: 9f3c1a7d2b6e
Revises: 6974e27e2fdc
Create Date: 2026-10-21 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f3c1a7d2b6e'
down_revision: Union[str, None] = '6974e27e2fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notifications',
        sa.Column(
            'category',
            sa.String(length=20),
            server_default='system',
            nullable=False,
            comment='health / order / system',
        ),
    )
    op.add_column(
        'notifications',
        sa.Column(
            'link',
            sa.String(length=255),
            nullable=True,
            comment='点击后跳转的前端路径',
        ),
    )
    op.add_column(
        'notifications',
        sa.Column(
            'dedupe_key',
            sa.String(length=120),
            nullable=True,
            comment='业务事件幂等键',
        ),
    )
    # MySQL 唯一索引允许多个 NULL，历史通知不受影响。
    op.create_index(
        'uq_notifications_user_dedupe',
        'notifications',
        ['user_id', 'dedupe_key'],
        unique=True,
    )
    op.create_index(
        'ix_notifications_user_read',
        'notifications',
        ['user_id', 'is_read'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index('uq_notifications_user_dedupe', table_name='notifications')
    op.drop_column('notifications', 'dedupe_key')
    op.drop_column('notifications', 'link')
    op.drop_column('notifications', 'category')
