from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KennelSize = Literal["small", "medium", "large"]


class KennelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    size: str
    status: str
    daily_price: float
    note: str | None = None


class KennelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    size: KennelSize
    status: Literal["available", "occupied", "cleaning", "maintenance"] = "available"
    daily_price: float = Field(gt=0, le=10000)
    note: str | None = None


class KennelUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    size: KennelSize | None = None
    status: Literal["available", "occupied", "cleaning", "maintenance"] | None = None
    daily_price: float | None = Field(default=None, gt=0, le=10000)
    note: str | None = None


class BoardingOrderCreate(BaseModel):
    pet_id: int
    kennel_id: int
    start_date: date
    end_date: date
    note: str | None = None


class BoardingOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    owner_id: int
    kennel_id: int
    start_date: date
    end_date: date
    status: str
    daily_price: float
    deposit: float
    total_amount: float
    payment_status: str = "unpaid"
    paid_amount: float = 0
    note: str | None = None
    confirmed_at: datetime | None = None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    draft_id: int | None = None
    pet_name: str | None = None
    kennel_code: str | None = None
    nights: int | None = None


class BoardingDraftCreate(BaseModel):
    pet_id: int
    kennel_id: int
    start_date: date
    end_date: date
    note: str | None = None
    # Agent 重试时复用同一个 key，避免重复生成草稿
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=80)


class BoardingDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    pet_id: int
    kennel_id: int
    start_date: date
    end_date: date
    daily_price: float
    total_amount: float
    status: str
    expires_at: datetime
    idempotency_key: str
    note: str | None = None
    pet_name: str | None = None
    kennel_code: str | None = None
    nights: int | None = None


class DraftConfirmRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)


class DailyReportCreate(BaseModel):
    report_date: date
    appetite: Literal["good", "normal", "poor"] | None = None
    stool: Literal["normal", "soft", "diarrhea"] | None = None
    spirit: Literal["good", "normal", "low"] | None = None
    note: str | None = None
    photos: list[str] | None = None


class DailyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    report_date: date
    appetite: str | None = None
    stool: str | None = None
    spirit: str | None = None
    note: str | None = None
    photos: list | None = None
    created_by: int | None = None
