from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefundOrder(Base):
    """一张成功支付单最多一笔全额退款，退款号同时作为渠道幂等键。"""

    __tablename__ = "refund_orders"

    refund_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payment_orders.id"), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("boarding_orders.id"), index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(String(300))
