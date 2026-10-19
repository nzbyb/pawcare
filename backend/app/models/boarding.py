from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JsonType


class Kennel(Base):
    __tablename__ = "kennels"
    __table_args__ = {"comment": "笼舍"}

    code: Mapped[str] = mapped_column(
        String(30), unique=True, index=True, nullable=False, comment="笼舍编号"
    )
    size: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="small / medium / large"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="available",
        nullable=False,
        comment="available / occupied / cleaning / maintenance",
    )
    daily_price: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), default=0, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)


class BoardingOrder(Base):
    __tablename__ = "boarding_orders"
    __table_args__ = (
        Index("ix_boarding_kennel_period", "kennel_id", "start_date", "end_date"),
        {"comment": "寄养订单"},
    )

    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    kennel_id: Mapped[int] = mapped_column(
        ForeignKey("kennels.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="pending/confirmed/checked_in/boarding/checked_out/completed/cancelled",
    )
    daily_price: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=False, default=0
    )
    deposit: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=False, default=0
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=False, default=0
    )
    note: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # 一张草稿最多生成一笔订单，用于确认接口的幂等返回
    draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("boarding_drafts.id", ondelete="SET NULL"),
        unique=True,
        index=True,
    )


class BoardingDailyReport(Base):
    __tablename__ = "boarding_daily_reports"
    __table_args__ = (
        UniqueConstraint("order_id", "report_date", name="uq_daily_report_order_date"),
        {"comment": "寄养日报"},
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("boarding_orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appetite: Mapped[str | None] = mapped_column(
        String(20), comment="good / normal / poor"
    )
    stool: Mapped[str | None] = mapped_column(
        String(20), comment="normal / soft / diarrhea"
    )
    spirit: Mapped[str | None] = mapped_column(
        String(20), comment="good / normal / low"
    )
    note: Mapped[str | None] = mapped_column(Text)
    photos: Mapped[list | None] = mapped_column(JsonType)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class MedicationLog(Base):
    __tablename__ = "medication_logs"
    __table_args__ = {"comment": "用药记录"}

    order_id: Mapped[int] = mapped_column(
        ForeignKey("boarding_orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    medication_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dose: Mapped[str | None] = mapped_column(String(50))
    given_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    given_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)


class BoardingDraft(Base):
    __tablename__ = "boarding_drafts"
    __table_args__ = {"comment": "Agent 生成的预约草稿"}

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kennel_id: Mapped[int] = mapped_column(
        ForeignKey("kennels.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_price: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=False, default=0
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="pending / confirmed / expired / cancelled",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="SET NULL"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)
