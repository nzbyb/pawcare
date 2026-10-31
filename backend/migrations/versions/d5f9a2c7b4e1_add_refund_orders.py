"""add full payment refund workflow

Revision ID: d5f9a2c7b4e1
Revises: b7d4f1c8e3a6
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f9a2c7b4e1"
down_revision = "b7d4f1c8e3a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refund_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("refund_no", sa.String(40), unique=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payment_orders.id"), unique=True, nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("boarding_orders.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("error", sa.String(300)),
    )
    op.create_index("ix_refund_orders_order_id", "refund_orders", ["order_id"])
    op.create_index("ix_refund_orders_status", "refund_orders", ["status"])


def downgrade():
    op.drop_table("refund_orders")
