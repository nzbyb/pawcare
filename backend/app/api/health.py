from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.health import (
    HealthRecordCreate,
    HealthRecordResponse,
    HealthRecordUpdate,
    ReminderResponse,
    ReminderUpdate,
)
from app.services import health_service

router = APIRouter(tags=["健康档案"])


@router.post("/pets/{pet_id}/health-records", response_model=Response)
def create_health_record(
    pet_id: int,
    data: HealthRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = health_service.create_record(db, current_user, pet_id, data)
    return Response.success(
        message="健康记录已保存",
        data=HealthRecordResponse.model_validate(record).model_dump(),
    )


@router.get("/pets/{pet_id}/health-records", response_model=Response)
def list_health_records(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = health_service.list_records(db, current_user, pet_id)
    return Response.success(
        data=[
            HealthRecordResponse.model_validate(record).model_dump()
            for record in records
        ]
    )


@router.put("/health-records/{record_id}", response_model=Response)
def update_health_record(
    record_id: int,
    data: HealthRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = health_service.update_record(db, current_user, record_id, data)
    return Response.success(
        message="健康记录已更新",
        data=HealthRecordResponse.model_validate(record).model_dump(),
    )


@router.delete("/health-records/{record_id}", response_model=Response)
def delete_health_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    health_service.delete_record(db, current_user, record_id)
    return Response.success(message="健康记录已删除")


@router.get("/pets/{pet_id}/reminders", response_model=Response)
def list_reminders(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reminders = health_service.list_reminders(db, current_user, pet_id)
    return Response.success(
        data=[ReminderResponse.model_validate(item).model_dump() for item in reminders]
    )


@router.patch("/pets/{pet_id}/reminders/{reminder_id}", response_model=Response)
def update_reminder(
    pet_id: int,
    reminder_id: int,
    data: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reminder = health_service.update_reminder(
        db, current_user, pet_id, reminder_id, data
    )
    return Response.success(
        message="提醒已处理" if data.status == "done" else "提醒已延后",
        data=ReminderResponse.model_validate(reminder).model_dump(),
    )
