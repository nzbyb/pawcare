"""add system settings and login logs

Revision ID: c7e2a4d9b1f6
Revises: f2b8c1d4e6a3
"""
from alembic import op
import sqlalchemy as sa

revision = "c7e2a4d9b1f6"
down_revision = "f2b8c1d4e6a3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(200)),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        comment="系统设置（键值）",
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    op.create_table(
        "login_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(40), nullable=False, server_default="success"),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        comment="登录日志",
    )
    op.create_index("ix_login_logs_user_id", "login_logs", ["user_id"])
    op.create_index("ix_login_logs_success", "login_logs", ["success"])
    op.create_index(
        "ix_login_logs_username_time", "login_logs", ["username", "create_time"]
    )


def downgrade():
    op.drop_table("login_logs")
    op.drop_table("system_settings")
