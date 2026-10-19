from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KennelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    size: str
    status: str
    daily_price: float
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
    note: str | None = None
    confirmed_at: datetime | None = None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None


class BoardingDraftCreate(BaseModel):
    pet_id: int
    kennel_id: int
    start_date: date
    end_date: date
    note: str | None = None


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
    note: str | None = None


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
