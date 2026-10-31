from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.health import HealthRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.health import (
    HealthRecordCreate,
    HealthRecordUpdate,
    ReminderUpdate,
)
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
        exists.title = f"{record.title} 到期提醒"
        exists.reminder_type = record.record_type
        exists.notified_at = None
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


def _reminder_dedupe_key(reminder: Reminder, due_date: date) -> str:
    if reminder.source_health_record_id is not None:
        return (
            f"health:{reminder.source_health_record_id}:"
            f"{reminder.reminder_type}:{due_date.isoformat()}"
        )
    return f"reminder:{reminder.id}:{due_date.isoformat()}"


def update_reminder(
    db: Session,
    user: User,
    pet_id: int,
    reminder_id: int,
    data: ReminderUpdate,
) -> Reminder:
    """完成或延后一条提醒。

    提醒属于健康档案，寄养员只能看不能改；完成 / 延后都会写审计日志。
    延后时同步 dedupe_key 并清空 notified_at，让新日期可以重新触发通知。
    """
    pet = pet_service.get_pet_for_write(db, user, pet_id)
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.pet_id != pet.id:
        raise BusinessException(message="提醒不存在")
    if reminder.status != "pending":
        raise BusinessException(message="该提醒已处理，请刷新后重试")
    if (data.status is None) == (data.snooze_days is None):
        raise BusinessException(message="请选择完成或延后")

    before = {
        "status": reminder.status,
        "due_date": reminder.due_date.isoformat(),
    }

    if data.status == "done":
        reminder.status = "done"
        action = "reminder.done"
    else:
        new_due_date = reminder.due_date + timedelta(days=data.snooze_days or 0)
        reminder.due_date = new_due_date
        reminder.notified_at = None
        candidate = _reminder_dedupe_key(reminder, new_due_date)
        conflict = (
            db.query(Reminder)
            .filter(Reminder.dedupe_key == candidate, Reminder.id != reminder.id)
            .first()
        )
        # 极端情况下新日期已有另一条提醒，用 snooze 前缀保证唯一。
        reminder.dedupe_key = (
            candidate
            if conflict is None
            else f"snooze:{reminder.id}:{new_due_date.isoformat()}"
        )
        action = "reminder.snooze"

    db.add(
        AuditLog(
            actor_id=user.id,
            action=action,
            target_type="reminder",
            target_id=reminder.id,
            before_data=before,
            after_data={
                "status": reminder.status,
                "due_date": reminder.due_date.isoformat(),
            },
        )
    )
    db.commit()
    db.refresh(reminder)
    return reminder
