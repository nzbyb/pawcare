from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecordType = Literal["vaccine", "deworm", "medication", "visit", "symptom"]


class HealthRecordCreate(BaseModel):
    record_type: RecordType
    title: str = Field(min_length=1, max_length=100)
    record_date: date
    next_due_date: date | None = None
    note: str | None = None
    extra: dict | None = None


class HealthRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    record_date: date | None = None
    next_due_date: date | None = None
    note: str | None = None
    extra: dict | None = None


class HealthRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    record_type: str
    title: str
    record_date: date
    next_due_date: date | None = None
    note: str | None = None
    extra: dict | None = None
    created_by: int | None = None
    deleted_at: datetime | None = None
    create_time: datetime | None = None


class ReminderUpdate(BaseModel):
    status: Literal["done"] | None = None
    snooze_days: int | None = Field(default=None, ge=1, le=90)


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    reminder_type: str
    title: str
    due_date: date
    status: str
    source_health_record_id: int | None = None
    notified_at: datetime | None = None
