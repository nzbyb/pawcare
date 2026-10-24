from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JsonType


class PaymentOrder(Base):
    """支付单。

    一笔寄养订单可以有多张支付单（例如超时关闭后重新发起），
    但同一时刻最多一张处于 created / paying 状态。
    """

    __tablename__ = "payment_orders"
    __table_args__ = (
        Index("ix_payment_order_status", "order_id", "status"),
        {"comment": "支付单"},
    )

    payment_no: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False, comment="商户支付单号"
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("boarding_orders.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(20), default="mock", nullable=False, comment="mock / alipay / wechat"
    )
    amount: Mapped[float] = mapped_column(
        Numeric(10, 2, asdecimal=False), nullable=False, comment="支付金额"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="created",
        nullable=False,
        index=True,
        comment="created / paying / paid / closed",
    )
    qr_token: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, comment="扫码支付凭证"
    )
    qr_content: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="二维码内容"
    )
    pay_url: Mapped[str | None] = mapped_column(
        Text, comment="渠道收银台地址（支付宝签名 URL 较长，单独存）"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="支付截止时间"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, comment="支付完成时间")
    transaction_id: Mapped[str | None] = mapped_column(
        String(80), comment="渠道交易号"
    )
    notify_payload: Mapped[dict | None] = mapped_column(
        JsonType, comment="渠道回调原文（脱敏后可留档）"
    )
