"""门户公告与意见反馈。

公告是"按角色推送 + 已读统计"的只读内容：发布后对所有可见角色生效，
已读记录按用户去重；反馈由用户提交、管理员回复，回复写站内通知。
两者都不触碰订单与支付，也不参与寄养状态机。
"""

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.content import Announcement, AnnouncementRead, Feedback
from app.models.user import User
from app.services import notification_service

CATEGORIES = ("notice", "policy", "activity")
AUDIENCES = ("all", "pet_owner", "boarding_staff", "admin")
STATUSES = ("draft", "published", "archived")
FEEDBACK_CATEGORIES = ("bug", "suggestion", "service", "other")
FEEDBACK_STATUSES = ("pending", "processing", "resolved", "closed")
MAX_PAGE_SIZE = 50


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    return page, page_size


def _visible(db: Session, user: User) -> list[int]:
    """当前用户可见的已发布公告 ID；管理员可见全部角色定向的公告。"""
    now = datetime.now()
    query = db.query(Announcement.id).filter(
        Announcement.status == "published",
        or_(Announcement.publish_at.is_(None), Announcement.publish_at <= now),
        or_(Announcement.expire_at.is_(None), Announcement.expire_at > now),
    )
    if user.role != "admin":
        query = query.filter(Announcement.audience.in_(("all", user.role)))
    return [row[0] for row in query.all()]


def _read_ids(db: Session, user: User, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    rows = (
        db.query(AnnouncementRead.announcement_id)
        .filter(
            AnnouncementRead.user_id == user.id,
            AnnouncementRead.announcement_id.in_(ids),
        )
        .all()
    )
    return {row[0] for row in rows}


def _item(row: Announcement, *, is_read: bool, read_count: int | None = None) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "category": row.category,
        "audience": row.audience,
        "is_pinned": row.is_pinned,
        "attachment_url": row.attachment_url,
        "publish_at": row.publish_at,
        "expire_at": row.expire_at,
        "create_time": row.create_time,
        "is_read": is_read,
        "read_count": read_count,
    }


def list_announcements(db: Session, user: User, limit: int = 20) -> dict:
    ids = _visible(db, user)
    if not ids:
        return {"items": [], "unread": 0}
    rows = (
        db.query(Announcement)
        .filter(Announcement.id.in_(ids))
        # 置顶优先，其次按上线时间（未填则按创建时间）倒序。
        .order_by(
            Announcement.is_pinned.desc(),
            func.coalesce(Announcement.publish_at, Announcement.create_time).desc(),
        )
        .limit(max(1, min(limit, 50)))
        .all()
    )
    read = _read_ids(db, user, [row.id for row in rows])
    return {
        "items": [_item(row, is_read=row.id in read) for row in rows],
        "unread": unread_count(db, user),
    }


def unread_count(db: Session, user: User) -> int:
    ids = _visible(db, user)
    if not ids:
        return 0
    read = _read_ids(db, user, ids)
    return len([announcement_id for announcement_id in ids if announcement_id not in read])


def get_announcement(db: Session, user: User, announcement_id: int, *, mark_read: bool = True) -> dict:
    if announcement_id not in set(_visible(db, user)):
        raise BusinessException(message="公告不存在或已下线", code=404)
    row = db.get(Announcement, announcement_id)
    if mark_read:
        exists = (
            db.query(AnnouncementRead.id)
            .filter(
                AnnouncementRead.announcement_id == announcement_id,
                AnnouncementRead.user_id == user.id,
            )
            .first()
        )
        if not exists:
            db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id))
            db.commit()
    detail = _item(row, is_read=True)
    detail.update(content=row.content, status=row.status)
    return detail


def mark_all_read(db: Session, user: User) -> int:
    ids = set(_visible(db, user))
    read = _read_ids(db, user, list(ids))
    missing = ids - read
    for announcement_id in sorted(missing):
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id))
    if missing:
        db.commit()
    return len(missing)


def _validate(data) -> None:
    if data.category not in CATEGORIES:
        raise BusinessException(message="公告分类不合法")
    if data.audience not in AUDIENCES:
        raise BusinessException(message="推送对象不合法")
    if data.status not in STATUSES:
        raise BusinessException(message="公告状态不合法")
    if data.publish_at and data.expire_at and data.expire_at <= data.publish_at:
        raise BusinessException(message="过期时间必须晚于上线时间")


def _read_count(db: Session, announcement_id: int) -> int:
    return (
        db.query(func.count(AnnouncementRead.id))
        .filter(AnnouncementRead.announcement_id == announcement_id)
        .scalar()
        or 0
    )


def list_for_admin(
    db: Session,
    *,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _pagination(page, page_size)
    if status and status not in STATUSES:
        raise BusinessException(message="公告状态不合法")
    query = db.query(Announcement)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Announcement.title.like(like), Announcement.content.like(like)))
    if status:
        query = query.filter(Announcement.status == status)
    total = query.count()
    rows = (
        query.order_by(Announcement.is_pinned.desc(), Announcement.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for row in rows:
        detail = _item(row, is_read=False, read_count=_read_count(db, row.id))
        detail.update(content=row.content, status=row.status)
        items.append(detail)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def create_announcement(db: Session, admin: User, data) -> Announcement:
    _validate(data)
    row = Announcement(
        title=data.title.strip(),
        category=data.category,
        content=data.content.strip(),
        audience=data.audience,
        status=data.status,
        is_pinned=data.is_pinned,
        attachment_url=data.attachment_url,
        publish_at=data.publish_at or (datetime.now() if data.status == "published" else None),
        expire_at=data.expire_at,
        created_by=admin.id,
    )
    db.add(row)
    db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="announcement.create",
            target_type="announcement",
            target_id=row.id,
            after_data={"title": row.title, "status": row.status, "audience": row.audience},
        )
    )
    db.commit()
    db.refresh(row)
    return row


def update_announcement(db: Session, admin: User, announcement_id: int, data) -> Announcement:
    _validate(data)
    row = db.get(Announcement, announcement_id)
    if not row:
        raise BusinessException(message="公告不存在", code=404)
    before = {"title": row.title, "status": row.status}
    row.title = data.title.strip()
    row.category = data.category
    row.content = data.content.strip()
    row.audience = data.audience
    row.status = data.status
    row.is_pinned = data.is_pinned
    row.attachment_url = data.attachment_url
    if data.publish_at:
        row.publish_at = data.publish_at
    elif data.status == "published":
        row.publish_at = row.publish_at or datetime.now()
    else:
        row.publish_at = None
    row.expire_at = data.expire_at
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="announcement.update",
            target_type="announcement",
            target_id=row.id,
            before_data=before,
            after_data={"title": row.title, "status": row.status, "audience": row.audience},
        )
    )
    db.commit()
    db.refresh(row)
    return row


def delete_announcement(db: Session, admin: User, announcement_id: int) -> None:
    row = db.get(Announcement, announcement_id)
    if not row:
        raise BusinessException(message="公告不存在", code=404)
    if row.status == "published":
        raise BusinessException(message="已发布的公告请先归档，再删除草稿或归档公告", code=409)
    before = {"title": row.title, "status": row.status}
    db.delete(row)
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="announcement.delete",
            target_type="announcement",
            target_id=announcement_id,
            before_data=before,
        )
    )
    db.commit()


def read_stats(db: Session, announcement_id: int) -> dict:
    row = db.get(Announcement, announcement_id)
    if not row:
        raise BusinessException(message="公告不存在", code=404)
    audience = AUDIENCES if row.audience == "all" else (row.audience,)
    if row.audience == "all":
        query = db.query(func.count(User.id)).filter(User.status == 1)
    else:
        query = db.query(func.count(User.id)).filter(
            User.status == 1, User.role.in_(audience)
        )
    target = query.scalar() or 0
    rows = (
        db.query(AnnouncementRead, User)
        .join(User, AnnouncementRead.user_id == User.id)
        .filter(AnnouncementRead.announcement_id == announcement_id)
        .order_by(AnnouncementRead.read_at.desc())
        .all()
    )
    readers = [
        {
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "role": user.role,
            "read_at": read.read_at,
        }
        for read, user in rows
    ]
    return {
        "announcement_id": announcement_id,
        "target": target,
        "read": len(readers),
        "unread": max(0, target - len(readers)),
        "readers": readers,
    }


def create_feedback(db: Session, user: User, data) -> Feedback:
    row = Feedback(
        user_id=user.id,
        category=data.category,
        content=data.content.strip(),
        contact=(data.contact or "").strip() or None,
    )
    db.add(row)
    db.flush()
    notification_service.notify_roles(
        db,
        ("admin",),
        "收到新的意见反馈",
        f"{user.nickname or user.username} 提交了一条反馈，等待处理。",
        category="system",
        link="/admin",
        dedupe_key=f"feedback:{row.id}:created",
    )
    db.commit()
    db.refresh(row)
    return row


def _feedback_payload(row: Feedback, user: User | None) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "category": row.category,
        "content": row.content,
        "contact": row.contact,
        "status": row.status,
        "reply": row.reply,
        "replied_at": row.replied_at,
        "create_time": row.create_time,
        "username": user.username if user else None,
        "nickname": user.nickname if user else None,
    }


def list_my_feedback(db: Session, user: User) -> list[dict]:
    rows = (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id)
        .order_by(Feedback.id.desc())
        .limit(50)
        .all()
    )
    return [_feedback_payload(row, user) for row in rows]


def list_feedback(
    db: Session,
    *,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _pagination(page, page_size)
    if status and status not in FEEDBACK_STATUSES:
        raise BusinessException(message="反馈状态不合法")
    query = db.query(Feedback, User).join(User, Feedback.user_id == User.id)
    if status:
        query = query.filter(Feedback.status == status)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(Feedback.content.like(like), User.username.like(like), User.nickname.like(like))
        )
    total = query.count()
    rows = (
        query.order_by(Feedback.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_feedback_payload(row, user) for row, user in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def reply_feedback(db: Session, admin: User, feedback_id: int, data) -> Feedback:
    if data.status not in FEEDBACK_STATUSES:
        raise BusinessException(message="反馈状态不合法")
    row = db.get(Feedback, feedback_id)
    if not row:
        raise BusinessException(message="反馈不存在", code=404)
    if data.status == "pending" and row.status != "pending":
        raise BusinessException(message="已处理过的反馈不能退回待处理", code=409)
    before = {"status": row.status}
    row.status = data.status
    if data.reply is not None and data.reply.strip():
        row.reply = data.reply.strip()
        row.replied_by = admin.id
        row.replied_at = datetime.now()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="feedback.reply",
            target_type="feedback",
            target_id=row.id,
            before_data=before,
            after_data={"status": row.status},
        )
    )
    if data.status in ("processing", "resolved", "closed"):
        notification_service.create_notification(
            db,
            row.user_id,
            "意见反馈已更新",
            f"你提交的反馈当前状态为{_status_label(row.status)}。"
            + (f"回复：{row.reply}" if row.reply else ""),
            category="system",
            link="/help",
            dedupe_key=f"feedback:{row.id}:{row.status}",
        )
    db.commit()
    db.refresh(row)
    return row


def _status_label(status: str) -> str:
    return {
        "pending": "待处理",
        "processing": "处理中",
        "resolved": "已解决",
        "closed": "已关闭",
    }.get(status, status)
