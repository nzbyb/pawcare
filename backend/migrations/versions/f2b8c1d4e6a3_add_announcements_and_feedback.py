"""add announcements, announcement reads and feedbacks

Revision ID: f2b8c1d4e6a3
Revises: d5f9a2c7b4e1
"""
from alembic import op
import sqlalchemy as sa

revision = "f2b8c1d4e6a3"
down_revision = "d5f9a2c7b4e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="notice"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False, server_default="all"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("attachment_url", sa.String(255)),
        sa.Column("publish_at", sa.DateTime()),
        sa.Column("expire_at", sa.DateTime()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        comment="门户公告",
    )
    op.create_index("ix_announcements_status_publish", "announcements", ["status", "publish_at"])
    op.create_index("ix_announcements_publish_at", "announcements", ["publish_at"])
    op.create_index("ix_announcements_created_by", "announcements", ["created_by"])

    op.create_table(
        "announcement_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=False),
        comment="公告已读记录",
    )
    op.create_index("uq_announcement_reads_user", "announcement_reads", ["announcement_id", "user_id"], unique=True)

    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("create_time", sa.DateTime(), nullable=False),
        sa.Column("update_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="suggestion"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reply", sa.Text()),
        sa.Column("replied_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("replied_at", sa.DateTime()),
        comment="帮助中心意见反馈",
    )
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
    op.create_index("ix_feedbacks_status_create", "feedbacks", ["status", "create_time"])


def downgrade():
    op.drop_table("feedbacks")
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
