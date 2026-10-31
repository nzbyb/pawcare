"""管理端只读视图与账号启停。

管理端刻意保持克制：这里只提供用户检索、笼舍占用和审计日志查询，
以及启用 / 停用账号这一个安全操作。订单状态机仍然只走寄养服务，
避免管理端绕开确认、入住、退房和支付的事务与审计。
"""

from datetime import date, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder, Kennel
from app.models.knowledge import KnowledgeChunk
from app.models.mcp import MCPAuditLog
from app.models.payment import PaymentOrder
from app.models.refund import RefundOrder
from app.models.pet import Pet
from app.models.reminder import Reminder
from app.models.user import User
from app.services.boarding_service import ACTIVE_ORDER_STATUSES

ROLES = ("pet_owner", "boarding_staff", "admin")
MAX_PAGE_SIZE = 50


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    return page, page_size


def _user_counts(db: Session, user_ids: list[int]) -> dict[int, dict[str, int]]:
    if not user_ids:
        return {}

    pets = dict(
        db.query(Pet.owner_id, func.count(Pet.id))
        .filter(Pet.owner_id.in_(user_ids), Pet.status == "active")
        .group_by(Pet.owner_id)
        .all()
    )
    orders = dict(
        db.query(BoardingOrder.owner_id, func.count(BoardingOrder.id))
        .filter(BoardingOrder.owner_id.in_(user_ids))
        .group_by(BoardingOrder.owner_id)
        .all()
    )
    return {
        user_id: {
            "pet_count": int(pets.get(user_id, 0)),
            "order_count": int(orders.get(user_id, 0)),
        }
        for user_id in user_ids
    }


def _user_payload(user: User, counts: dict[str, int] | None = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "role": user.role,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "create_time": user.create_time,
        "pet_count": (counts or {}).get("pet_count", 0),
        "order_count": (counts or {}).get("order_count", 0),
    }


def overview(db: Session) -> dict:
    """管理端概览：账号、宠物、订单、实收和知识库规模，只读聚合。"""
    today = date.today()
    soon = today + timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = (
        db.query(func.count(User.id)).filter(User.status == 1).scalar() or 0
    )
    role_counts = dict(
        db.query(User.role, func.count(User.id))
        .filter(User.status == 1)
        .group_by(User.role)
        .all()
    )

    total_pets = (
        db.query(func.count(Pet.id)).filter(Pet.status == "active").scalar() or 0
    )

    total_orders = db.query(func.count(BoardingOrder.id)).scalar() or 0
    active_orders = (
        db.query(func.count(BoardingOrder.id))
        .filter(BoardingOrder.status.in_(ACTIVE_ORDER_STATUSES))
        .scalar()
        or 0
    )
    completed_orders = (
        db.query(func.count(BoardingOrder.id))
        .filter(BoardingOrder.status == "completed")
        .scalar()
        or 0
    )
    today_check_in = (
        db.query(func.count(BoardingOrder.id))
        .filter(func.date(BoardingOrder.checked_in_at) == today.isoformat())
        .scalar()
        or 0
    )
    today_check_out = (
        db.query(func.count(BoardingOrder.id))
        .filter(func.date(BoardingOrder.checked_out_at) == today.isoformat())
        .scalar()
        or 0
    )
    paid_total = (
        db.query(func.coalesce(func.sum(PaymentOrder.amount), 0))
        .filter(PaymentOrder.status == "paid")
        .scalar()
        or 0
    )

    refunded_total = db.query(func.coalesce(func.sum(RefundOrder.amount), 0)).filter(
        RefundOrder.status == "succeeded",
    ).scalar() or 0

    pending_reminders = (
        db.query(func.count(Reminder.id))
        .filter(Reminder.status == "pending")
        .scalar()
        or 0
    )
    due_soon = (
        db.query(func.count(Reminder.id))
        .filter(Reminder.status == "pending", Reminder.due_date <= soon)
        .scalar()
        or 0
    )

    knowledge_documents = (
        db.query(func.count(func.distinct(KnowledgeChunk.doc_id))).scalar() or 0
    )
    knowledge_chunks = db.query(func.count(KnowledgeChunk.id)).scalar() or 0

    return {
        "date": today,
        "users": {
            "total": total_users,
            "active": active_users,
            "owners": role_counts.get("pet_owner", 0),
            "staff": role_counts.get("boarding_staff", 0),
            "admins": role_counts.get("admin", 0),
        },
        "pets": {"active": total_pets},
        "orders": {
            "total": total_orders,
            "active": active_orders,
            "completed": completed_orders,
            "today_check_in": today_check_in,
            "today_check_out": today_check_out,
        },
        "revenue": {"paid_total": float(paid_total), "refunded_total": float(refunded_total),
                    "net_total": round(float(paid_total) - float(refunded_total), 2)},
        "reminders": {"pending": pending_reminders, "due_soon": due_soon},
        "knowledge": {
            "documents": knowledge_documents,
            "chunks": knowledge_chunks,
        },
    }


def statistics(db: Session, days: int = 30) -> dict:
    if days not in (7, 30):
        raise BusinessException(message="请选择最近7天或30天")
    today = date.today()
    start = today - timedelta(days=days - 1)
    end = today + timedelta(days=1)
    bookings = {str(day): count for day, count in db.query(func.date(BoardingOrder.create_time), func.count(BoardingOrder.id))
                    .filter(BoardingOrder.create_time >= start, BoardingOrder.create_time < end)
                    .group_by(func.date(BoardingOrder.create_time)).all()}
    receipts = {str(day): amount for day, amount in db.query(func.date(PaymentOrder.paid_at), func.sum(PaymentOrder.amount))
                   .filter(PaymentOrder.status == "paid", PaymentOrder.paid_at >= start, PaymentOrder.paid_at < end)
                   .group_by(func.date(PaymentOrder.paid_at)).all()}
    refunds = {str(day): amount for day, amount in db.query(func.date(RefundOrder.completed_at), func.sum(RefundOrder.amount))
                  .filter(RefundOrder.status == "succeeded", RefundOrder.completed_at >= start, RefundOrder.completed_at < end)
                  .group_by(func.date(RefundOrder.completed_at)).all()}
    rows = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        received, refunded = float(receipts.get(day, 0)), float(refunds.get(day, 0))
        rows.append({"date": day, "orders": bookings.get(day, 0), "received": received,
                     "refunded": refunded, "net": round(received - refunded, 2)})
    kennels = db.query(func.count(Kennel.id)).scalar() or 0
    actual = db.query(func.count(func.distinct(BoardingOrder.kennel_id))).filter(
        BoardingOrder.status.in_(("checked_in", "boarding")),
    ).scalar() or 0
    return {
        "start_date": start, "end_date": today, "daily": rows,
        "orders": sum(row["orders"] for row in rows),
        "received": round(sum(row["received"] for row in rows), 2),
        "refunded": round(sum(row["refunded"] for row in rows), 2),
        "net": round(sum(row["net"] for row in rows), 2),
        "occupancy_rate": round(actual / kennels * 100, 1) if kennels else 0,
        "actual_occupied": actual, "kennel_total": kennels,
    }


def list_knowledge(
    db: Session,
    *,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _pagination(page, page_size)

    query = db.query(KnowledgeChunk)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                KnowledgeChunk.title.like(like),
                KnowledgeChunk.content.like(like),
                KnowledgeChunk.doc_id.like(like),
            )
        )

    total = query.count()
    rows = (
        query.order_by(KnowledgeChunk.doc_id, KnowledgeChunk.chunk_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for chunk in rows:
        meta = chunk.meta or {}
        items.append(
            {
                "id": chunk.id,
                "doc_id": chunk.doc_id,
                "chunk_index": chunk.chunk_index,
                "title": chunk.title,
                "category": meta.get("category"),
                "source": meta.get("source"),
                "content": chunk.content,
                "has_embedding": bool(chunk.embedding),
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_users(
    db: Session,
    *,
    keyword: str | None = None,
    role: str | None = None,
    status: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _pagination(page, page_size)
    if role and role not in ROLES:
        raise BusinessException(message="角色不合法")

    query = db.query(User)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                User.username.like(like),
                User.nickname.like(like),
                User.email.like(like),
                User.phone.like(like),
            )
        )
    if role:
        query = query.filter(User.role == role)
    if status is not None:
        query = query.filter(User.status == status)

    total = query.count()
    users = (
        query.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    counts = _user_counts(db, [user.id for user in users])
    return {
        "items": [_user_payload(user, counts.get(user.id)) for user in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def set_user_status(db: Session, admin: User, user_id: int, status: int) -> User:
    if status not in (0, 1):
        raise BusinessException(message="账号状态不合法")

    user = db.get(User, user_id)
    if not user:
        raise BusinessException(message="用户不存在", code=404)
    if user.id == admin.id:
        raise BusinessException(message="不能停用自己的账号")
    if status == 0 and user.role == "admin":
        others = (
            db.query(User.id)
            .filter(
                User.role == "admin",
                User.status == 1,
                User.id != user.id,
            )
            .count()
        )
        if others == 0:
            raise BusinessException(message="至少保留一个可用的管理员")

    before = {"status": user.status}
    user.status = status
    if status == 0:
        # 停用后立即踢掉已登录的会话，不用等令牌自然过期。
        user.token_version = (user.token_version or 0) + 1

    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.enable" if status == 1 else "user.disable",
            target_type="user",
            target_id=user.id,
            before_data=before,
            after_data={"status": status},
        )
    )
    db.commit()
    db.refresh(user)
    return user


def kennel_occupancy(db: Session, day: date | None = None) -> dict:
    day = day or date.today()
    kennels = db.query(Kennel).order_by(Kennel.code).all()

    orders = (
        db.query(BoardingOrder)
        .filter(
            or_(
                and_(
                    BoardingOrder.status.in_(ACTIVE_ORDER_STATUSES),
                    BoardingOrder.start_date <= day, BoardingOrder.end_date > day,
                ),
                # 今天及未来的预测：实际在住优先，逾期后退房时间待核实。
                and_(
                    BoardingOrder.status.in_(("checked_in", "boarding")),
                    day >= date.today(),
                    or_(BoardingOrder.end_date > day, BoardingOrder.end_date <= date.today()),
                ),
            ),
        )
        .order_by(BoardingOrder.status.in_(("checked_in", "boarding")).desc(), BoardingOrder.start_date)
        .all()
    )
    pets = {
        pet.id: pet
        for pet in db.query(Pet)
        .filter(Pet.id.in_({order.pet_id for order in orders}))
        .all()
    }
    owners = {
        user.id: user
        for user in db.query(User)
        .filter(User.id.in_({order.owner_id for order in orders}))
        .all()
    }

    occupancy: dict[int, dict] = {}
    for order in orders:
        pet = pets.get(order.pet_id)
        owner = owners.get(order.owner_id)
        occupancy.setdefault(
            order.kennel_id,
            {
                "order_id": order.id,
                "order_status": order.status,
                "is_actual_stay": order.status in ("checked_in", "boarding"),
                "overdue": order.status in ("checked_in", "boarding") and order.end_date < day,
                "payment_status": order.payment_status,
                "pet_name": pet.name if pet else "宠物",
                "pet_species": pet.species if pet else None,
                "owner_name": (owner.nickname or owner.username) if owner else "—",
                "owner_phone": owner.phone if owner else None,
                "start_date": order.start_date,
                "end_date": order.end_date,
            },
        )

    items = []
    for kennel in kennels:
        current = occupancy.get(kennel.id)
        if current:
            display_status = "occupied"
        elif kennel.status == "occupied":
            # 笼舍的 occupied 由入住 / 退房维护，可能因历史数据残留；
            # 没有在住订单时按空闲展示，避免出现“占用中但没有客人”。
            display_status = "available"
        else:
            display_status = kennel.status
        items.append(
            {
                "id": kennel.id,
                "code": kennel.code,
                "size": kennel.size,
                "status": kennel.status,
                "display_status": display_status,
                "daily_price": kennel.daily_price,
                "note": kennel.note,
                "occupancy": current,
            }
        )

    occupied = sum(1 for item in items if item["display_status"] == "occupied")
    blocked = sum(
        1 for item in items if item["display_status"] in ("cleaning", "maintenance")
    )
    return {
        "date": day,
        "summary": {
            "total": len(items),
            "occupied": occupied,
            "available": len(items) - occupied - blocked,
            "blocked": blocked,
        },
        "items": items,
    }


def list_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _pagination(page, page_size)

    query = db.query(AuditLog, User).outerjoin(User, AuditLog.actor_id == User.id)
    if action and action.strip():
        query = query.filter(AuditLog.action.like(f"{action.strip()}%"))

    total = query.count()
    rows = (
        query.order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for log, actor in rows:
        items.append(
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "actor_name": (
                    (actor.nickname or actor.username) if actor else "系统"
                ),
                "actor_username": actor.username if actor else None,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "before_data": log.before_data,
                "after_data": log.after_data,
                "trace_id": log.trace_id,
                "ip": log.ip,
                "create_time": log.create_time,
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_mcp_audit(
    db: Session,
    *,
    user_id: int | None = None,
    tool: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """MCP 调用审计：只读查询，按时间倒序。"""
    page, page_size = _pagination(page, page_size)

    query = db.query(MCPAuditLog, User).outerjoin(
        User, MCPAuditLog.user_id == User.id
    )
    if user_id is not None:
        query = query.filter(MCPAuditLog.user_id == user_id)
    if tool and tool.strip():
        query = query.filter(MCPAuditLog.tool_name == tool.strip())
    if status and status.strip():
        query = query.filter(MCPAuditLog.status == status.strip())

    total = query.count()
    rows = (
        query.order_by(
            MCPAuditLog.create_time.desc(), MCPAuditLog.id.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_name": (
                (user.nickname or user.username) if user else "已删除用户"
            ),
            "username": user.username if user else None,
            "transport": log.transport,
            "tool_name": log.tool_name,
            "arguments": log.arguments,
            "status": log.status,
            "error_code": log.error_code,
            "elapsed_ms": log.elapsed_ms,
            "ip": log.ip,
            "trace_id": log.trace_id,
            "create_time": log.create_time,
        }
        for log, user in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
