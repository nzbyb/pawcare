from datetime import datetime

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.health import HealthRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.health import HealthRecordCreate, HealthRecordUpdate
from app.services import pet_service


def _get_record(db: Session, user: User, record_id: int, write: bool = False) -> HealthRecord:
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at is not None:
        raise BusinessException(message="健康记录不存在")
    if write:
        pet_service.get_pet_for_write(db, user, record.pet_id)
    else:
        pet_service.get_pet(db, user, record.pet_id)
    return record


def _sync_reminder(db: Session, record: HealthRecord) -> None:
    """健康记录变化时同步提醒。

    - 先把这条记录之前生成的待处理提醒置为 dismissed；
    - 有 next_due_date 时再建一条新的，dedupe_key 保证重复扫描不会重复插入。
    """
    db.query(Reminder).filter(
        Reminder.source_health_record_id == record.id,
        Reminder.status == "pending",
    ).update({"status": "dismissed"}, synchronize_session=False)

    if record.next_due_date is None:
        return

    dedupe_key = (
        f"health:{record.id}:{record.record_type}:{record.next_due_date.isoformat()}"
    )
    exists = db.query(Reminder).filter(Reminder.dedupe_key == dedupe_key).first()
    if exists:
        # 改回曾经用过的日期时，复用原提醒并重新激活，避免 dedupe_key 阻塞。
        exists.status = "pending"
        return

    db.add(
        Reminder(
            pet_id=record.pet_id,
            reminder_type=record.record_type,
            title=f"{record.title} 到期提醒",
            due_date=record.next_due_date,
            dedupe_key=dedupe_key,
            source_health_record_id=record.id,
        )
    )


def create_record(
    db: Session, user: User, pet_id: int, data: HealthRecordCreate
) -> HealthRecord:
    pet = pet_service.get_pet_for_write(db, user, pet_id)
    record = HealthRecord(pet_id=pet.id, created_by=user.id, **data.model_dump())
    db.add(record)
    db.flush()
    _sync_reminder(db, record)
    db.commit()
    db.refresh(record)
    return record


def list_records(
    db: Session, user: User, pet_id: int, include_deleted: bool = False
) -> list[HealthRecord]:
    pet = pet_service.get_pet(db, user, pet_id)
    query = db.query(HealthRecord).filter(HealthRecord.pet_id == pet.id)
    if not include_deleted:
        query = query.filter(HealthRecord.deleted_at.is_(None))
    return query.order_by(HealthRecord.record_date.desc()).all()


def update_record(
    db: Session, user: User, record_id: int, data: HealthRecordUpdate
) -> HealthRecord:
    record = _get_record(db, user, record_id, write=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    _sync_reminder(db, record)
    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, user: User, record_id: int) -> None:
    record = _get_record(db, user, record_id, write=True)
    record.deleted_at = datetime.now()
    db.query(Reminder).filter(
        Reminder.source_health_record_id == record.id,
        Reminder.status == "pending",
    ).update({"status": "dismissed"}, synchronize_session=False)
    db.commit()


def list_reminders(db: Session, user: User, pet_id: int) -> list[Reminder]:
    pet = pet_service.get_pet(db, user, pet_id)
    return (
        db.query(Reminder)
        .filter(Reminder.pet_id == pet.id, Reminder.status == "pending")
        .order_by(Reminder.due_date.asc())
        .all()
    )
