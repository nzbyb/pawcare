"""add payment pay_url

Revision ID: b7d4f1c8e3a6
Revises: a1b7c3d9e5f2
Create Date: 2026-10-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d4f1c8e3a6'
down_revision: Union[str, None] = 'a1b7c3d9e5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'payment_orders',
        sa.Column(
            'pay_url',
            sa.Text(),
            nullable=True,
            comment='渠道收银台地址（支付宝签名 URL 较长，单独存）',
        ),
    )


def downgrade() -> None:
    op.drop_column('payment_orders', 'pay_url')
