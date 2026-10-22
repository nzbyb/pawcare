"""站内通知。

通知在业务动作发生时写入（订单确认、入住、退房、日报、支付），
健康提醒则在读取通知列表时惰性补齐：项目没有常驻调度器，
用户打开页面就能看到 7 天内到期或已逾期的提醒。
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.pet import Pet
from app.models.reminder import Notification, Reminder
from app.models.user import User

REMINDER_WINDOW_DAYS = 7


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    *,
    category: str = "system",
    link: str | None = None,
    dedupe_key: str | None = None,
) -> Notification | None:
    """写入一条通知；dedupe_key 命中或用户关闭该类通知时跳过。"""
    user = db.get(User, user_id)
    if not user or not getattr(user, f"notify_{category}", True):
        return None

    if dedupe_key:
        exists = (
            db.query(Notification.id)
            .filter(
                Notification.user_id == user_id,
                Notification.dedupe_key == dedupe_key,
            )
            .first()
        )
        if exists:
            return None

    notice = Notification(
        user_id=user_id,
        category=category,
        title=title,
        content=content,
        link=link,
        dedupe_key=dedupe_key,
    )
    db.add(notice)
    return notice


def notify_roles(
    db: Session,
    roles: tuple[str, ...],
    title: str,
    content: str,
    *,
    category: str = "order",
    link: str | None = None,
    dedupe_key: str | None = None,
    exclude_user_id: int | None = None,
) -> int:
    """给某个角色的所有正常用户发通知，返回实际写入条数。"""
    query = db.query(User.id).filter(User.role.in_(roles), User.status == 1)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    count = 0
    for (user_id,) in query.all():
        if create_notification(
            db,
            user_id,
            title,
            content,
            category=category,
            link=link,
            dedupe_key=dedupe_key,
        ):
            count += 1
    return count


def _reminder_content(reminder: Reminder, days: int) -> str:
    if days < 0:
        return f"{reminder.title} 已过期 {-days} 天，请尽快处理。"
    if days == 0:
        return f"{reminder.title} 今天到期。"
    return f"{reminder.title} 还有 {days} 天到期。"


def sync_due_reminders(db: Session, user: User) -> int:
    """把该用户 7 天内到期或已逾期的健康提醒补成站内通知。"""
    if user.role != "pet_owner":
        return 0

    today = date.today()
    rows = (
        db.query(Reminder, Pet)
        .join(Pet, Reminder.pet_id == Pet.id)
        .filter(
            Pet.owner_id == user.id,
            Pet.status == "active",
            Reminder.status == "pending",
            Reminder.due_date <= today + timedelta(days=REMINDER_WINDOW_DAYS),
        )
        .all()
    )

    created = 0
    for reminder, pet in rows:
        days = (reminder.due_date - today).days
        notice = create_notification(
            db,
            user.id,
            f"健康提醒 · {pet.name}",
            _reminder_content(reminder, days),
            category="health",
            link=f"/pets/{pet.id}",
            dedupe_key=f"reminder:{reminder.id}:{reminder.due_date.isoformat()}",
        )
        if notice:
            created += 1

    if created:
        db.commit()
    return created


def sync_all_reminders(db: Session) -> int:
    """扫描全部正常宠物主，供定时任务调用；逐用户提交，单用户失败不影响其他人。"""
    user_ids = (
        db.query(User.id)
        .filter(User.role == "pet_owner", User.status == 1)
        .all()
    )
    created = 0
    for (user_id,) in user_ids:
        user = db.get(User, user_id)
        if user is not None:
            created += sync_due_reminders(db, user)
    return created


def list_notifications(
    db: Session, user: User, limit: int = 10, unread_only: bool = False
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return (
        query.order_by(Notification.create_time.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


def unread_count(db: Session, user: User) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
        .count()
    )


def mark_read(db: Session, user: User, notification_id: int) -> int:
    notice = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
        .first()
    )
    if not notice:
        raise BusinessException(message="通知不存在", code=404)
    if not notice.is_read:
        notice.is_read = True
        db.commit()
    return unread_count(db, user)


def mark_all_read(db: Session, user: User) -> int:
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    ).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return 0
