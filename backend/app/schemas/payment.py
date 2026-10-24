from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    order_id: int = Field(gt=0)


class MockNotifyRequest(BaseModel):
    payment_no: str = Field(min_length=8, max_length=40)
    token: str = Field(min_length=8, max_length=80)


class PaymentResponse(BaseModel):
    payment_no: str
    order_id: int
    channel: Literal["mock", "alipay", "wechat"]
    amount: float
    status: Literal["created", "paying", "paid", "closed"]
    qr_content: str
    pay_url: str | None = None
    expires_at: datetime
    owner_id: int
    paid_at: datetime | None = None
    transaction_id: str | None = None
    create_time: datetime


class PublicPaymentResponse(BaseModel):
    """扫码支付页可见的信息：不含 owner_id、交易号等内部字段。"""

    payment_no: str
    order_id: int
    channel: Literal["mock", "alipay", "wechat"]
    amount: float
    status: Literal["created", "paying", "paid", "closed"]
    qr_content: str
    pay_url: str | None = None
    expires_at: datetime
