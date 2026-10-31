from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KennelSize = Literal["small", "medium", "large"]


class BoardingHealthItem(BaseModel):
    code: str
    title: str
    level: Literal["warning", "info", "ok"]
    detail: str
    source_record_id: int | None = None
    record_date: date | None = None
    next_due_date: date | None = None


class BoardingHealthCheck(BaseModel):
    pet_id: int
    pet_name: str
    start_date: date
    end_date: date
    checked_on: date
    status: Literal["attention", "ready"]
    warning_count: int
    summary: str
    notice: str
    items: list[BoardingHealthItem]


class BoardingTaskItem(BaseModel):
    order_id: int
    pet_id: int
    pet_name: str
    kennel_code: str
    start_date: date
    end_date: date
    status: str
    payment_status: str
    report_id: int | None = None
    report_date: date | None = None
    abnormal_reasons: list[str] = Field(default_factory=list)


class BoardingTasks(BaseModel):
    date: date
    counts: dict[str, int]
    pending: list[BoardingTaskItem]
    arrivals: list[BoardingTaskItem]
    departures: list[BoardingTaskItem]
    missing_reports: list[BoardingTaskItem]
    abnormal_reports: list[BoardingTaskItem]


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
    refund: dict | None = None
    refunded_amount: float = 0
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
    health_check: BoardingHealthCheck | None = None


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


class HandoverHealthRecord(BaseModel):
    record_type: str
    title: str
    record_date: date
    next_due_date: date | None = None
    note: str | None = None


class HandoverReminder(BaseModel):
    title: str
    due_date: date
    status: str


class HandoverPet(BaseModel):
    name: str
    species: str
    breed: str | None = None
    gender: str | None = None
    neutered: bool
    birthday: date | None = None
    allergies: str | None = None
    notes: str | None = None
    latest_weight: float | None = None
    latest_weight_date: date | None = None


class HandoverOwner(BaseModel):
    nickname: str
    phone: str | None = None
    email: str | None = None


class HandoverResponse(BaseModel):
    order: BoardingOrderResponse
    pet: HandoverPet
    owner: HandoverOwner
    health_records: list[HandoverHealthRecord]
    reminders: list[HandoverReminder]
    generated_at: datetime
