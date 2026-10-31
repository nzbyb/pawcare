from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        Index("ix_announcements_status_publish", "status", "publish_at"),
        {"comment": "门户公告"},
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(
        String(20),
        default="notice",
        server_default="notice",
        nullable=False,
        comment="notice 通知 / policy 政策 / activity 活动",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(
        String(20),
        default="all",
        server_default="all",
        nullable=False,
        comment="all / pet_owner / boarding_staff / admin",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        server_default="draft",
        nullable=False,
        comment="draft / published / archived",
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    attachment_url: Mapped[str | None] = mapped_column(
        String(255), comment="附件地址，前端展示为下载链接"
    )
    publish_at: Mapped[datetime | None] = mapped_column(
        DateTime, index=True, comment="上线时间，早于当前时间的已发布公告才展示"
    )
    expire_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="过期时间，留空表示长期有效"
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        Index("uq_announcement_reads_user", "announcement_id", "user_id", unique=True),
        {"comment": "公告已读记录"},
    )

    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        Index("ix_feedbacks_status_create", "status", "create_time"),
        {"comment": "帮助中心意见反馈"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(20),
        default="suggestion",
        server_default="suggestion",
        nullable=False,
        comment="bug / suggestion / service / other",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(
        String(100), comment="可选联系方式，便于回访"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
        comment="pending / processing / resolved / closed",
    )
    reply: Mapped[str | None] = mapped_column(Text)
    replied_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    replied_at: Mapped[datetime | None] = mapped_column(DateTime)
