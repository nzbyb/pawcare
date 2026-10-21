"""add notification preferences

Revision ID: c4e8b1f6a2d9
Revises: 9f3c1a7d2b6e
Create Date: 2026-10-21 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8b1f6a2d9'
down_revision: Union[str, None] = '9f3c1a7d2b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'notify_health',
            sa.Boolean(),
            server_default='1',
            nullable=False,
            comment='接收健康提醒',
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'notify_order',
            sa.Boolean(),
            server_default='1',
            nullable=False,
            comment='接收订单动态',
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'notify_system',
            sa.Boolean(),
            server_default='1',
            nullable=False,
            comment='接收系统通知',
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'notify_system')
    op.drop_column('users', 'notify_order')
    op.drop_column('users', 'notify_health')
