"""寄养业务服务。

这里有一个刻意的边界：**确认草稿不是 Agent 工具**。
Agent 只能生成 pending 草稿；订单必须由用户在独立的 REST 接口里确认。
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.boarding import (
    BoardingDailyReport,
    BoardingDraft,
    BoardingOrder,
    Kennel,
)
from app.models.health import HealthRecord
from app.models.pet import Pet, WeightRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.boarding import (
    BoardingDraftCreate,
    BoardingDraftResponse,
    BoardingOrderResponse,
    DailyReportCreate,
    KennelCreate,
    KennelUpdate,
)
from app.services import notification_service

# pending 的订单也占用档期，避免两个用户同时确认后撞车
ACTIVE_ORDER_STATUSES = ("pending", "confirmed", "checked_in", "boarding")
ORDER_STATUSES = ACTIVE_ORDER_STATUSES + ("completed", "cancelled")
DRAFT_TTL_MINUTES = 15
MAX_STAY_NIGHTS = 60
DEPOSIT_RATE = 0.3


def _audit(
    db: Session,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            after_data=after,
        )
    )


def _pet_name(db: Session, pet_id: int) -> str:
    pet = db.get(Pet, pet_id)
    return pet.name if pet else "宠物"


def _validate_period(start_date, end_date) -> int:
    if end_date <= start_date:
        raise BusinessException(message="退房日期必须晚于入住日期")
    nights = (end_date - start_date).days
    if nights > MAX_STAY_NIGHTS:
        raise BusinessException(message=f"单次寄养不能超过 {MAX_STAY_NIGHTS} 晚")
    return nights


def _has_overlap(
    db: Session,
    kennel_id: int,
    start_date,
    end_date,
    exclude_order_id: int | None = None,
) -> bool:
    """半开区间 [start, end) 的重叠判断。"""
    query = db.query(BoardingOrder.id).filter(
        BoardingOrder.kennel_id == kennel_id,
        BoardingOrder.status.in_(ACTIVE_ORDER_STATUSES),
        BoardingOrder.start_date < end_date,
        BoardingOrder.end_date > start_date,
    )
    if exclude_order_id is not None:
        query = query.filter(BoardingOrder.id != exclude_order_id)
    return query.first() is not None


def _get_kennel(db: Session, kennel_id: int) -> Kennel:
    kennel = db.get(Kennel, kennel_id)
    if not kennel:
        raise BusinessException(message="笼舍不存在")
    if kennel.status == "maintenance":
        raise BusinessException(message="该笼舍正在维护")
    return kennel


def list_kennels(db: Session) -> list[Kennel]:
    return db.query(Kennel).order_by(Kennel.code.asc()).all()


def check_availability(
    db: Session, start_date, end_date, size: str | None = None
) -> list[Kennel]:
    _validate_period(start_date, end_date)
    occupied = db.query(BoardingOrder.kennel_id).filter(
        BoardingOrder.status.in_(ACTIVE_ORDER_STATUSES),
        BoardingOrder.start_date < end_date,
        BoardingOrder.end_date > start_date,
    )
    query = db.query(Kennel).filter(
        Kennel.status != "maintenance",
        ~Kennel.id.in_(occupied),
    )
    if size:
        query = query.filter(Kennel.size == size)
    return query.order_by(Kennel.daily_price.asc(), Kennel.code.asc()).all()


def create_kennel(db: Session, user: User, data: KennelCreate) -> Kennel:
    if user.role != "admin":
        raise BusinessException(message="只有管理员可以维护笼舍", code=403)
    if db.query(Kennel).filter(Kennel.code == data.code).first():
        raise BusinessException(message="笼舍编号已存在")

    kennel = Kennel(**data.model_dump())
    db.add(kennel)
    db.flush()
    _audit(db, user.id, "kennel.create", "kennel", kennel.id)
    db.commit()
    db.refresh(kennel)
    return kennel


def update_kennel(
    db: Session, user: User, kennel_id: int, data: KennelUpdate
) -> Kennel:
    if user.role != "admin":
        raise BusinessException(message="只有管理员可以维护笼舍", code=403)
    kennel = db.get(Kennel, kennel_id)
    if not kennel:
        raise BusinessException(message="笼舍不存在")

    changes = data.model_dump(exclude_unset=True)
    if "code" in changes:
        exists = (
            db.query(Kennel)
            .filter(Kennel.code == changes["code"], Kennel.id != kennel.id)
            .first()
        )
        if exists:
            raise BusinessException(message="笼舍编号已存在")
    for field, value in changes.items():
        setattr(kennel, field, value)
    _audit(db, user.id, "kennel.update", "kennel", kennel.id, after=changes)
    db.commit()
    db.refresh(kennel)
    return kennel


def _find_by_idempotency_key(db: Session, key: str) -> BoardingDraft | None:
    return (
        db.query(BoardingDraft)
        .filter(BoardingDraft.idempotency_key == key)
        .first()
    )


def create_draft(db: Session, user: User, data: BoardingDraftCreate) -> BoardingDraft:
    if user.role != "pet_owner":
        raise BusinessException(message="只有宠物主可以预约寄养", code=403)

    pet = db.get(Pet, data.pet_id)
    if not pet or pet.status == "deleted":
        raise BusinessException(message="宠物不存在")
    if pet.owner_id != user.id:
        raise BusinessException(message="无权为该宠物预约", code=403)

    nights = _validate_period(data.start_date, data.end_date)
    kennel = _get_kennel(db, data.kennel_id)

    key = data.idempotency_key
    if key:
        existing = _find_by_idempotency_key(db, key)
        if existing:
            if existing.owner_id != user.id:
                raise BusinessException(message="幂等键已被占用", code=409)
            same_request = (
                existing.pet_id == data.pet_id
                and existing.kennel_id == data.kennel_id
                and existing.start_date == data.start_date
                and existing.end_date == data.end_date
            )
            if not same_request:
                raise BusinessException(message="幂等键已用于其他预约", code=409)
            if (
                existing.status == "pending"
                and existing.expires_at <= datetime.now()
            ):
                existing.status = "expired"
                db.commit()
                raise BusinessException(message="草稿已过期，请重新生成", code=409)
            return existing
    else:
        key = uuid4().hex

    if _has_overlap(db, kennel.id, data.start_date, data.end_date):
        raise BusinessException(message="该笼舍在所选日期已被预订", code=409)

    daily_price = float(kennel.daily_price)
    total_amount = round(daily_price * nights, 2)
    draft = BoardingDraft(
        owner_id=user.id,
        pet_id=pet.id,
        kennel_id=kennel.id,
        start_date=data.start_date,
        end_date=data.end_date,
        daily_price=daily_price,
        total_amount=total_amount,
        status="pending",
        expires_at=datetime.now() + timedelta(minutes=DRAFT_TTL_MINUTES),
        idempotency_key=key,
        note=data.note,
    )
    db.add(draft)
    db.flush()
    _audit(
        db,
        user.id,
        "boarding_draft.create",
        "boarding_draft",
        draft.id,
        after={
            "pet_id": pet.id,
            "kennel_id": kennel.id,
            "start_date": data.start_date.isoformat(),
            "end_date": data.end_date.isoformat(),
            "total_amount": total_amount,
        },
    )
    db.commit()
    db.refresh(draft)
    return draft


def _get_own_draft(
    db: Session, user: User, draft_id: int, lock: bool = False
) -> BoardingDraft:
    query = db.query(BoardingDraft).filter(BoardingDraft.id == draft_id)
    if lock:
        query = query.with_for_update()
    draft = query.first()
    if not draft:
        raise BusinessException(message="草稿不存在")
    if user.role == "pet_owner" and draft.owner_id != user.id:
        raise BusinessException(message="无权访问该草稿", code=403)
    if user.role == "boarding_staff":
        raise BusinessException(message="无权访问该草稿", code=403)
    return draft


def get_draft(db: Session, user: User, draft_id: int) -> BoardingDraft:
    draft = _get_own_draft(db, user, draft_id)
    if draft.status == "pending" and draft.expires_at <= datetime.now():
        draft.status = "expired"
        db.commit()
        db.refresh(draft)
    return draft


def list_drafts(db: Session, user: User) -> list[BoardingDraft]:
    query = db.query(BoardingDraft)
    if user.role == "pet_owner":
        query = query.filter(BoardingDraft.owner_id == user.id)
    elif user.role != "admin":
        raise BusinessException(message="无权访问草稿", code=403)

    drafts = query.order_by(BoardingDraft.id.desc()).all()
    now = datetime.now()
    changed = False
    for draft in drafts:
        if draft.status == "pending" and draft.expires_at <= now:
            draft.status = "expired"
            changed = True
    if changed:
        db.commit()
    return drafts


def cancel_draft(db: Session, user: User, draft_id: int) -> None:
    draft = _get_own_draft(db, user, draft_id, lock=True)
    if draft.status == "confirmed":
        raise BusinessException(message="草稿已生成订单，不能取消", code=409)
    if draft.status != "pending":
        raise BusinessException(message="草稿已失效", code=409)

    draft.status = "cancelled"
    _audit(db, user.id, "boarding_draft.cancel", "boarding_draft", draft.id)
    db.commit()


def confirm_draft(
    db: Session, user: User, draft_id: int, idempotency_key: str
) -> BoardingOrder:
    """用户点击确认后才会创建订单。Agent 没有这个工具。"""
    if user.role != "pet_owner":
        raise BusinessException(message="只有宠物主可以确认预约", code=403)

    draft = _get_own_draft(db, user, draft_id, lock=True)
    if idempotency_key != draft.idempotency_key:
        raise BusinessException(message="确认键不匹配", code=400)

    if draft.status == "confirmed":
        order = (
            db.query(BoardingOrder)
            .filter(BoardingOrder.draft_id == draft.id)
            .first()
        )
        if order:
            return order
        raise BusinessException(message="草稿状态异常，请联系管理员", code=409)

    if draft.status != "pending":
        raise BusinessException(message="草稿已失效，请重新生成", code=409)

    if draft.expires_at <= datetime.now():
        draft.status = "expired"
        db.commit()
        raise BusinessException(message="草稿已过期，请重新生成", code=409)

    # 锁住笼舍行，把同一笼舍的确认请求串行化（MySQL 行锁 + 写事务）；
    kennel = (
        db.query(Kennel)
        .filter(Kennel.id == draft.kennel_id)
        .with_for_update()
        .first()
    )
    if not kennel:
        raise BusinessException(message="笼舍不存在")
    if kennel.status == "maintenance":
        raise BusinessException(message="该笼舍正在维护", code=409)
    if _has_overlap(db, kennel.id, draft.start_date, draft.end_date):
        db.rollback()
        raise BusinessException(message="笼舍刚刚被预订，请重新选择", code=409)

    nights = (draft.end_date - draft.start_date).days
    order = BoardingOrder(
        pet_id=draft.pet_id,
        owner_id=draft.owner_id,
        kennel_id=draft.kennel_id,
        start_date=draft.start_date,
        end_date=draft.end_date,
        status="pending",
        daily_price=draft.daily_price,
        deposit=round(float(draft.total_amount) * DEPOSIT_RATE, 2),
        total_amount=draft.total_amount,
        note=draft.note,
        created_by=user.id,
        draft_id=draft.id,
    )
    db.add(order)
    draft.status = "confirmed"
    try:
        db.flush()
        _audit(
            db,
            user.id,
            "boarding_draft.confirm",
            "boarding_order",
            order.id,
            after={
                "draft_id": draft.id,
                "kennel_id": kennel.id,
                "start_date": draft.start_date.isoformat(),
                "end_date": draft.end_date.isoformat(),
                "total_amount": float(order.total_amount),
                "nights": nights,
            },
        )
        pet_name = _pet_name(db, order.pet_id)
        notification_service.create_notification(
            db,
            order.owner_id,
            "预约已提交",
            f"{pet_name} 的寄养预约已生成，等待寄养员确认。",
            category="order",
            link="/boarding",
            dedupe_key=f"order:{order.id}:created",
        )
        notification_service.notify_roles(
            db,
            ("boarding_staff",),
            "新的寄养预约",
            f"{pet_name} 的寄养订单待确认。",
            category="order",
            link="/boarding",
            dedupe_key=f"order:{order.id}:staff_new",
        )
        db.commit()
    except IntegrityError:
        # 并发确认时另一条请求可能已经生成订单，回滚后返回已有订单。
        db.rollback()
        existing = (
            db.query(BoardingOrder)
            .filter(BoardingOrder.draft_id == draft_id)
            .first()
        )
        if existing:
            return existing
        raise BusinessException(message="预约确认失败，请重试", code=409)

    db.refresh(order)
    return order


def _get_order(db: Session, user: User, order_id: int) -> BoardingOrder:
    order = db.get(BoardingOrder, order_id)
    if not order:
        raise BusinessException(message="订单不存在")
    if user.role == "pet_owner" and order.owner_id != user.id:
        raise BusinessException(message="无权访问该订单", code=403)
    return order


def get_order(db: Session, user: User, order_id: int) -> BoardingOrder:
    return _get_order(db, user, order_id)


def list_orders(
    db: Session, user: User, status: str | None = None
) -> list[BoardingOrder]:
    if status and status not in ORDER_STATUSES:
        raise BusinessException(message="订单状态不合法")

    query = db.query(BoardingOrder)
    if user.role == "pet_owner":
        query = query.filter(BoardingOrder.owner_id == user.id)
    if status:
        query = query.filter(BoardingOrder.status == status)
    return query.order_by(BoardingOrder.start_date.desc(), BoardingOrder.id.desc()).all()


def confirm_order(db: Session, user: User, order_id: int) -> BoardingOrder:
    if user.role not in ("boarding_staff", "admin"):
        raise BusinessException(message="只有寄养员可以确认订单", code=403)
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在")
    if order.status == "confirmed":
        return order
    if order.status != "pending":
        raise BusinessException(message="当前订单状态不能确认", code=409)

    order.status = "confirmed"
    order.confirmed_at = datetime.now()
    _audit(db, user.id, "boarding_order.confirm", "boarding_order", order.id)
    notification_service.create_notification(
        db,
        order.owner_id,
        "寄养订单已确认",
        f"{_pet_name(db, order.pet_id)} 的寄养预约已由寄养员确认。",
        category="order",
        link="/boarding",
        dedupe_key=f"order:{order.id}:confirmed",
    )
    db.commit()
    db.refresh(order)
    return order


def check_in(db: Session, user: User, order_id: int) -> BoardingOrder:
    if user.role not in ("boarding_staff", "admin"):
        raise BusinessException(message="只有寄养员可以办理入住", code=403)
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在")
    if order.status == "checked_in":
        return order
    if order.status != "confirmed":
        raise BusinessException(message="只有已确认的订单可以入住", code=409)

    kennel = db.query(Kennel).filter(Kennel.id == order.kennel_id).with_for_update().first()
    if not kennel:
        raise BusinessException(message="笼舍不存在")
    if kennel.status == "maintenance":
        raise BusinessException(message="该笼舍正在维护", code=409)

    occupied = (
        db.query(BoardingOrder)
        .filter(
            BoardingOrder.kennel_id == order.kennel_id,
            BoardingOrder.id != order.id,
            BoardingOrder.status.in_(("checked_in", "boarding")),
        )
        .first()
    )
    if occupied:
        raise BusinessException(message="该笼舍已有宠物入住", code=409)

    boarding_elsewhere = (
        db.query(BoardingOrder)
        .filter(
            BoardingOrder.pet_id == order.pet_id,
            BoardingOrder.id != order.id,
            BoardingOrder.status.in_(("checked_in", "boarding")),
        )
        .first()
    )
    if boarding_elsewhere:
        raise BusinessException(message="该宠物已在其他寄养订单中入住", code=409)

    order.status = "checked_in"
    order.checked_in_at = datetime.now()
    kennel.status = "occupied"
    _audit(db, user.id, "boarding_order.check_in", "boarding_order", order.id)
    notification_service.create_notification(
        db,
        order.owner_id,
        "宠物已入住",
        f"{_pet_name(db, order.pet_id)} 已办理入住，寄养期间可查看每日日报。",
        category="order",
        link="/boarding",
        dedupe_key=f"order:{order.id}:checked_in",
    )
    db.commit()
    db.refresh(order)
    return order


def check_out(db: Session, user: User, order_id: int) -> BoardingOrder:
    if user.role not in ("boarding_staff", "admin"):
        raise BusinessException(message="只有寄养员可以办理退房", code=403)
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在")
    if order.status == "completed":
        return order
    if order.status != "checked_in":
        raise BusinessException(message="只有入住中的订单可以退房", code=409)

    order.status = "completed"
    order.checked_out_at = datetime.now()
    kennel = db.get(Kennel, order.kennel_id)
    if kennel and kennel.status == "occupied":
        kennel.status = "available"
    _audit(db, user.id, "boarding_order.check_out", "boarding_order", order.id)
    notification_service.create_notification(
        db,
        order.owner_id,
        "寄养已结束",
        f"{_pet_name(db, order.pet_id)} 已办理退房，感谢使用 PawCare。",
        category="order",
        link="/boarding",
        dedupe_key=f"order:{order.id}:checked_out",
    )
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, user: User, order_id: int) -> BoardingOrder:
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在")
    if user.role == "pet_owner" and order.owner_id != user.id:
        raise BusinessException(message="无权操作该订单", code=403)
    if order.status == "cancelled":
        return order
    if order.status not in ("pending", "confirmed"):
        raise BusinessException(message="当前订单状态不能取消", code=409)

    order.status = "cancelled"
    _audit(db, user.id, "boarding_order.cancel", "boarding_order", order.id)
    pet_name = _pet_name(db, order.pet_id)
    if user.id == order.owner_id:
        # 宠物主取消后通知寄养员，避免档期空出来却没人知道。
        notification_service.notify_roles(
            db,
            ("boarding_staff",),
            "寄养订单已取消",
            f"{pet_name} 的寄养订单已被宠物主取消。",
            category="order",
            link="/boarding",
            dedupe_key=f"order:{order.id}:cancelled",
            exclude_user_id=user.id,
        )
    else:
        notification_service.create_notification(
            db,
            order.owner_id,
            "寄养订单已取消",
            f"{pet_name} 的寄养订单已取消。",
            category="order",
            link="/boarding",
            dedupe_key=f"order:{order.id}:cancelled",
        )
    db.commit()
    db.refresh(order)
    return order


def add_daily_report(
    db: Session, user: User, order_id: int, data: DailyReportCreate
) -> BoardingDailyReport:
    if user.role not in ("boarding_staff", "admin"):
        raise BusinessException(message="只有寄养员可以填写日报", code=403)
    order = db.get(BoardingOrder, order_id)
    if not order:
        raise BusinessException(message="订单不存在")
    if order.status not in ("checked_in", "boarding", "completed"):
        raise BusinessException(message="该订单还不能填写日报", code=409)
    if not (order.start_date <= data.report_date <= order.end_date):
        raise BusinessException(message="日报日期必须在寄养日期范围内")

    exists = (
        db.query(BoardingDailyReport)
        .filter(
            BoardingDailyReport.order_id == order.id,
            BoardingDailyReport.report_date == data.report_date,
        )
        .first()
    )
    if exists:
        raise BusinessException(message="该日期已有日报，请勿重复填写", code=409)

    report = BoardingDailyReport(
        order_id=order.id,
        created_by=user.id,
        **data.model_dump(),
    )
    db.add(report)
    db.flush()
    _audit(db, user.id, "boarding_report.create", "boarding_report", report.id)
    notification_service.create_notification(
        db,
        order.owner_id,
        "今日寄养日报已更新",
        f"{_pet_name(db, order.pet_id)} 在 {data.report_date.isoformat()} 的日报已填写。",
        category="order",
        link="/boarding",
        dedupe_key=f"order:{order.id}:report:{data.report_date.isoformat()}",
    )
    db.commit()
    db.refresh(report)
    return report


def list_daily_reports(
    db: Session, user: User, order_id: int
) -> list[BoardingDailyReport]:
    order = _get_order(db, user, order_id)
    return (
        db.query(BoardingDailyReport)
        .filter(BoardingDailyReport.order_id == order.id)
        .order_by(BoardingDailyReport.report_date.desc())
        .all()
    )


def draft_payload(db: Session, draft: BoardingDraft) -> dict:
    payload = BoardingDraftResponse.model_validate(draft)
    pet = db.get(Pet, draft.pet_id)
    kennel = db.get(Kennel, draft.kennel_id)
    payload.pet_name = pet.name if pet else None
    payload.kennel_code = kennel.code if kennel else None
    payload.nights = (draft.end_date - draft.start_date).days
    return payload.model_dump()


def order_payload(db: Session, order: BoardingOrder) -> dict:
    payload = BoardingOrderResponse.model_validate(order)
    pet = db.get(Pet, order.pet_id)
    kennel = db.get(Kennel, order.kennel_id)
    payload.pet_name = pet.name if pet else None
    payload.kennel_code = kennel.code if kennel else None
    payload.nights = (order.end_date - order.start_date).days
    return payload.model_dump()


def handover_payload(db: Session, user: User, order_id: int) -> dict:
    """寄养交接单：订单 + 宠物健康摘要 + 主人联系方式，供前台打印签字。"""
    order = _get_order(db, user, order_id)
    pet = db.get(Pet, order.pet_id)
    if not pet or pet.status == "deleted":
        raise BusinessException(message="宠物档案不存在", code=404)
    owner = db.get(User, order.owner_id)

    records = (
        db.query(HealthRecord)
        .filter(
            HealthRecord.pet_id == pet.id,
            HealthRecord.deleted_at.is_(None),
        )
        .order_by(HealthRecord.record_date.desc(), HealthRecord.id.desc())
        .limit(12)
        .all()
    )
    reminders = (
        db.query(Reminder)
        .filter(Reminder.pet_id == pet.id, Reminder.status == "pending")
        .order_by(Reminder.due_date.asc())
        .all()
    )
    weight = (
        db.query(WeightRecord)
        .filter(WeightRecord.pet_id == pet.id)
        .order_by(WeightRecord.record_date.desc(), WeightRecord.id.desc())
        .first()
    )

    return {
        "order": order_payload(db, order),
        "pet": {
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "gender": pet.gender,
            "neutered": pet.neutered,
            "birthday": pet.birthday,
            "allergies": pet.allergies,
            "notes": pet.notes,
            "latest_weight": float(weight.weight_kg) if weight else None,
            "latest_weight_date": weight.record_date if weight else None,
        },
        "owner": {
            "nickname": owner.nickname if owner else "未知",
            "phone": owner.phone if owner else None,
            "email": owner.email if owner else None,
        },
        "health_records": [
            {
                "record_type": record.record_type,
                "title": record.title,
                "record_date": record.record_date,
                "next_due_date": record.next_due_date,
                "note": record.note,
            }
            for record in records
        ],
        "reminders": [
            {
                "title": reminder.title,
                "due_date": reminder.due_date,
                "status": reminder.status,
            }
            for reminder in reminders
        ],
        "generated_at": datetime.now(),
    }
