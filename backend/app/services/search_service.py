"""站内搜索：宠物、寄养订单、公告、护理知识。

搜索结果按当前用户的权限过滤：宠物主只能搜到自己的宠物与订单；
护理知识属于管理端只读内容，只对管理员开放。每个分组最多返回 limit 条，
不提供跨分组全量分页，避免退化成另一套列表页。
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.boarding import BoardingOrder, Kennel
from app.models.content import Announcement
from app.models.knowledge import KnowledgeChunk
from app.models.pet import Pet
from app.models.user import User
from app.services import content_service

MAX_KEYWORD = 50
DEFAULT_LIMIT = 5

SPECIES_LABELS = {"dog": "犬", "cat": "猫"}
ORDER_STATUS_LABELS = {
    "pending": "待确认",
    "confirmed": "已确认",
    "checked_in": "已入住",
    "boarding": "寄养中",
    "checked_out": "已退房",
    "completed": "已完成",
    "cancelled": "已取消",
}


def _search_pets(db: Session, user: User, like: str, limit: int) -> list[dict]:
    query = db.query(Pet).filter(
        Pet.status != "deleted",
        or_(Pet.name.like(like), Pet.breed.like(like)),
    )
    if user.role == "pet_owner":
        query = query.filter(Pet.owner_id == user.id)

    items = []
    for pet in query.order_by(Pet.create_time.desc()).limit(limit).all():
        species = SPECIES_LABELS.get(pet.species, pet.species or "宠物")
        items.append(
            {
                "type": "pet",
                "id": pet.id,
                "title": pet.name,
                "subtitle": f"{species} · {pet.breed or '品种未填写'}",
                "url": f"/pets/{pet.id}",
            }
        )
    return items


def _search_orders(db: Session, user: User, like: str, limit: int) -> list[dict]:
    query = (
        db.query(BoardingOrder, Pet, Kennel)
        .join(Pet, BoardingOrder.pet_id == Pet.id)
        .join(Kennel, BoardingOrder.kennel_id == Kennel.id)
        .filter(or_(Pet.name.like(like), Kennel.code.like(like)))
    )
    if user.role == "pet_owner":
        query = query.filter(BoardingOrder.owner_id == user.id)

    items = []
    rows = query.order_by(BoardingOrder.start_date.desc(), BoardingOrder.id.desc()).limit(limit).all()
    for order, pet, kennel in rows:
        status = ORDER_STATUS_LABELS.get(order.status, order.status)
        items.append(
            {
                "type": "order",
                "id": order.id,
                "title": f"#{order.id} {pet.name}",
                "subtitle": (
                    f"{kennel.code} · {order.start_date} → {order.end_date} · {status}"
                ),
                "url": f"/boarding?order={order.id}",
            }
        )
    return items


def _search_announcements(db: Session, user: User, like: str, limit: int) -> list[dict]:
    ids = content_service.visible_ids(db, user)
    if not ids:
        return []
    rows = (
        db.query(Announcement)
        .filter(
            Announcement.id.in_(ids),
            or_(Announcement.title.like(like), Announcement.content.like(like)),
        )
        .order_by(Announcement.is_pinned.desc(), Announcement.create_time.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "type": "announcement",
            "id": row.id,
            "title": row.title,
            "subtitle": row.content[:60] + ("…" if len(row.content) > 60 else ""),
            "url": f"/announcements?id={row.id}",
        }
        for row in rows
    ]


def _search_knowledge(db: Session, like: str, limit: int) -> list[dict]:
    rows = (
        db.query(KnowledgeChunk)
        .filter(
            or_(KnowledgeChunk.title.like(like), KnowledgeChunk.content.like(like))
        )
        .order_by(KnowledgeChunk.doc_id, KnowledgeChunk.chunk_index)
        .limit(limit)
        .all()
    )
    return [
        {
            "type": "knowledge",
            "id": row.id,
            "title": row.title,
            "subtitle": (row.meta or {}).get("category") or row.doc_id,
            "url": "/admin",
        }
        for row in rows
    ]


def search(db: Session, user: User, keyword: str, limit: int = DEFAULT_LIMIT) -> dict:
    q = (keyword or "").strip()
    if not q:
        raise BusinessException(message="请输入搜索关键词")
    q = q[:MAX_KEYWORD]
    like = f"%{q}%"
    limit = max(1, min(limit, 10))

    groups = [
        ("pet", "宠物档案", _search_pets(db, user, like, limit)),
        ("order", "寄养订单", _search_orders(db, user, like, limit)),
        ("announcement", "公告", _search_announcements(db, user, like, limit)),
    ]
    if user.role == "admin":
        groups.append(("knowledge", "护理知识", _search_knowledge(db, like, limit)))

    payload = [
        {"type": group_type, "label": label, "items": items}
        for group_type, label, items in groups
        if items
    ]
    return {
        "keyword": q,
        "total": sum(len(group["items"]) for group in payload),
        "groups": payload,
    }
