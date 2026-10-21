from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = {"comment": "健康提醒"}

    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reminder_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="vaccine / deworm / medication"
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    # 幂等键：pet + type + date + source，APScheduler 重复扫描不会产生重复提醒
    dedupe_key: Mapped[str] = mapped_column(
        String(120), unique=True, index=True, nullable=False
    )
    source_health_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("health_records.id", ondelete="SET NULL"), index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # 同一用户同一条业务事件只通知一次；dedupe_key 为 NULL 的通知不受限制。
        Index("uq_notifications_user_dedupe", "user_id", "dedupe_key", unique=True),
        Index("ix_notifications_user_read", "user_id", "is_read"),
        {"comment": "站内通知"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(20),
        default="system",
        server_default="system",
        nullable=False,
        comment="health / order / system",
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(
        String(255), comment="点击后跳转的前端路径"
    )
    dedupe_key: Mapped[str | None] = mapped_column(
        String(120), comment="业务事件幂等键"
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
