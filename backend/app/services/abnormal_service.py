"""异常日报处置闭环。

日报记录食欲、排便、精神三项；任意一项异常就在写日报的同一事务里生成一张处置单，
后续按「认领 → 处置 → 告知宠物主」推进。处置单与日报一一对应（report_id 唯一），
同一份日报不会因为重复提交产生第二张单。

严重度规则：出现腹泻或精神低落，或同时出现两项以上异常，记为紧急；
其余单项异常记为关注。紧急异常在生成处置单时就通知宠物主，避免评估前干等。
"""

from datetime import date, datetime

from sqlalchemy import case as sql_case
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.boarding import (
    BoardingAbnormalCase,
    BoardingDailyReport,
    BoardingOrder,
    Kennel,
)
from app.models.pet import Pet
from app.models.user import User
from app.services import notification_service

REASON_LABELS = {
    "appetite_poor": "食欲较差",
    "stool_soft": "便便偏软",
    "stool_diarrhea": "腹泻",
    "spirit_low": "精神低落",
}
CRITICAL_REASONS = ("stool_diarrhea", "spirit_low")
SEVERITIES = ("warning", "critical")
SEVERITY_LABELS = {"warning": "关注", "critical": "紧急"}
STATUSES = ("open", "processing", "resolved")
HANDLING_ROLES = ("boarding_staff", "admin")
MAX_ACTION_CHARS = 500


def _audit(
    db: Session,
    actor_id: int | None,
    action: str,
    case_id: int,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type="boarding_abnormal_case",
            target_id=case_id,
            before_data=before,
            after_data=after,
        )
    )


def report_reasons(report: BoardingDailyReport) -> list[str]:
    reasons = []
    if report.appetite == "poor":
        reasons.append("appetite_poor")
    if report.stool == "soft":
        reasons.append("stool_soft")
    elif report.stool == "diarrhea":
        reasons.append("stool_diarrhea")
    if report.spirit == "low":
        reasons.append("spirit_low")
    return reasons


def severity_for(reasons: list[str]) -> str:
    if any(reason in CRITICAL_REASONS for reason in reasons) or len(reasons) >= 2:
        return "critical"
    return "warning"


def _pet(db: Session, order: BoardingOrder) -> Pet | None:
    return db.get(Pet, order.pet_id)


def _reason_text(reasons: list[str] | None) -> str:
    return "、".join(REASON_LABELS.get(reason, reason) for reason in reasons or [])


def sync_report_case(
    db: Session, report: BoardingDailyReport, actor_id: int | None = None
) -> BoardingAbnormalCase | None:
    """日报写入后调用：异常则建单，正常则返回 None。调用方负责 commit。"""
    reasons = report_reasons(report)
    if not reasons:
        return None

    exists = (
        db.query(BoardingAbnormalCase)
        .filter(BoardingAbnormalCase.report_id == report.id)
        .first()
    )
    if exists:
        return exists

    order = db.get(BoardingOrder, report.order_id)
    case = BoardingAbnormalCase(
        order_id=report.order_id,
        report_id=report.id,
        severity=severity_for(reasons),
        reasons=reasons,
        status="open",
    )
    db.add(case)
    db.flush()
    _audit(db, actor_id, "abnormal_case.create", case.id, after=_snapshot(case))

    pet = _pet(db, order)
    pet_name = pet.name if pet else "宠物"
    severity_label = SEVERITY_LABELS[case.severity]
    notification_service.notify_roles(
        db,
        HANDLING_ROLES,
        f"{severity_label}异常待处置：{pet_name}",
        f"{report.report_date.isoformat()} 的日报出现{_reason_text(reasons)}，请尽快认领并处置。",
        category="order",
        link="/",
        dedupe_key=f"abnormal:{case.id}:staff",
        exclude_user_id=actor_id,
    )
    if case.severity == "critical" and order is not None:
        notification_service.create_notification(
            db,
            order.owner_id,
            f"{pet_name}出现{_reason_text(reasons)}，护理员正在处理",
            "这是系统根据今日寄养日报自动发出的提醒，处置完成后会再次告知你结果。",
            category="order",
            link="/boarding",
            dedupe_key=f"abnormal:{case.id}:owner:alert",
        )
    return case


def _snapshot(case: BoardingAbnormalCase) -> dict:
    return {
        "status": case.status,
        "severity": case.severity,
        "reasons": list(case.reasons or []),
        "handler_id": case.handler_id,
        "action_taken": case.action_taken,
        "vet_contacted": case.vet_contacted,
        "owner_notified": case.owner_notified,
    }


def _serialize(db: Session, case: BoardingAbnormalCase) -> dict:
    order = db.get(BoardingOrder, case.order_id)
    report = db.get(BoardingDailyReport, case.report_id)
    pet = db.get(Pet, order.pet_id) if order else None
    kennel = db.get(Kennel, order.kennel_id) if order else None
    owner = db.get(User, order.owner_id) if order else None
    handler = db.get(User, case.handler_id) if case.handler_id else None
    resolver = db.get(User, case.resolved_by) if case.resolved_by else None
    reasons = list(case.reasons or [])
    return {
        "id": case.id,
        "order_id": case.order_id,
        "report_id": case.report_id,
        "report_date": report.report_date if report else None,
        "pet_id": order.pet_id if order else None,
        "pet_name": pet.name if pet else None,
        "kennel_code": kennel.code if kennel else None,
        "order_status": order.status if order else None,
        "owner_id": order.owner_id if order else None,
        "owner_name": (owner.nickname or owner.username) if owner else None,
        "severity": case.severity,
        "severity_label": SEVERITY_LABELS.get(case.severity, case.severity),
        "reasons": reasons,
        "reason_labels": [REASON_LABELS.get(reason, reason) for reason in reasons],
        "status": case.status,
        "handler_id": case.handler_id,
        "handler_name": (handler.nickname or handler.username) if handler else None,
        "claimed_at": case.claimed_at,
        "resolved_at": case.resolved_at,
        "resolved_by": case.resolved_by,
        "resolver_name": (resolver.nickname or resolver.username) if resolver else None,
        "action_taken": case.action_taken,
        "vet_contacted": case.vet_contacted,
        "owner_notified": case.owner_notified,
        "report": {
            "appetite": report.appetite if report else None,
            "stool": report.stool if report else None,
            "spirit": report.spirit if report else None,
            "note": report.note if report else None,
        },
        "create_time": case.create_time,
    }


def _scoped_query(db: Session, user: User, order_id: int | None = None):
    query = db.query(BoardingAbnormalCase).join(
        BoardingOrder, BoardingAbnormalCase.order_id == BoardingOrder.id
    )
    if user.role == "pet_owner":
        query = query.filter(BoardingOrder.owner_id == user.id)
    if order_id is not None:
        query = query.filter(BoardingAbnormalCase.order_id == order_id)
    return query


def list_cases(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    severity: str | None = None,
    order_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    if status and status not in STATUSES:
        raise BusinessException(message="处置状态不合法")
    if severity and severity not in SEVERITIES:
        raise BusinessException(message="严重度不合法")
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)

    scope = _scoped_query(db, user, order_id)
    counts = {"open": 0, "processing": 0, "resolved": 0, "critical_open": 0}
    for case_status, count in (
        scope.with_entities(
            BoardingAbnormalCase.status, func.count(BoardingAbnormalCase.id)
        )
        .group_by(BoardingAbnormalCase.status)
        .all()
    ):
        counts[case_status] = count
    counts["critical_open"] = scope.filter(
        BoardingAbnormalCase.status.in_(("open", "processing")),
        BoardingAbnormalCase.severity == "critical",
    ).count()

    query = scope
    if status:
        query = query.filter(BoardingAbnormalCase.status == status)
    if severity:
        query = query.filter(BoardingAbnormalCase.severity == severity)
    total = query.count()
    # 未结的单排在前面，其余按时间倒序，寄养员打开就看到待办。
    order_by_resolved = sql_case(
        (BoardingAbnormalCase.status == "resolved", 1), else_=0
    )
    rows = (
        query.order_by(
            order_by_resolved.asc(),
            BoardingAbnormalCase.create_time.desc(),
            BoardingAbnormalCase.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_serialize(db, case) for case in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
        "stats": stats(db) if user.role in HANDLING_ROLES else None,
        "today": date.today(),
    }


def case_detail(db: Session, user: User, case_id: int) -> dict:
    case = _scoped_query(db, user).filter(BoardingAbnormalCase.id == case_id).first()
    if not case:
        raise BusinessException(message="处置单不存在", code=404)
    return _serialize(db, case)


def _get_case(db: Session, user: User, case_id: int) -> BoardingAbnormalCase:
    if user.role not in HANDLING_ROLES:
        raise BusinessException(message="只有寄养员和管理员可以处置异常", code=403)
    case = db.get(BoardingAbnormalCase, case_id)
    if not case:
        raise BusinessException(message="处置单不存在", code=404)
    return case


def claim(db: Session, user: User, case_id: int) -> dict:
    """认领：open → processing，同一时间只有一个人负责。"""
    case = _get_case(db, user, case_id)
    if case.status == "resolved":
        raise BusinessException(message="该异常已处置完成", code=409)
    if case.status == "processing" and case.handler_id != user.id:
        handler = db.get(User, case.handler_id) if case.handler_id else None
        name = (handler.nickname or handler.username) if handler else "其他寄养员"
        raise BusinessException(message=f"该异常已由{name}认领", code=409)

    before = _snapshot(case)
    case.handler_id = user.id
    case.claimed_at = case.claimed_at or datetime.now()
    case.status = "processing"
    _audit(db, user.id, "abnormal_case.claim", case.id, before=before, after=_snapshot(case))
    db.commit()
    db.refresh(case)
    return _serialize(db, case)


def resolve(
    db: Session,
    user: User,
    case_id: int,
    *,
    action_taken: str,
    vet_contacted: bool = False,
    notify_owner: bool = True,
) -> dict:
    """处置：写入措施并结单，可选择把结果告知宠物主。"""
    case = _get_case(db, user, case_id)
    if case.status == "resolved":
        raise BusinessException(message="该异常已处置完成", code=409)
    if (
        case.handler_id is not None
        and case.handler_id != user.id
        and user.role != "admin"
    ):
        handler = db.get(User, case.handler_id)
        name = (handler.nickname or handler.username) if handler else "其他寄养员"
        raise BusinessException(message=f"该异常由{name}负责，如需接手请对方先交接", code=409)
    action = (action_taken or "").strip()
    if len(action) < 2:
        raise BusinessException(message="请填写处置措施")
    if len(action) > MAX_ACTION_CHARS:
        raise BusinessException(message=f"处置措施不能超过 {MAX_ACTION_CHARS} 字")

    before = _snapshot(case)
    now = datetime.now()
    case.status = "resolved"
    case.action_taken = action
    case.vet_contacted = vet_contacted
    case.resolved_at = now
    case.resolved_by = user.id
    if case.handler_id is None:
        case.handler_id = user.id
        case.claimed_at = now

    notice = None
    if notify_owner:
        order = db.get(BoardingOrder, case.order_id)
        pet = db.get(Pet, order.pet_id) if order else None
        pet_name = pet.name if pet else "宠物"
        summary = f"护理员已处置：{action}"
        if vet_contacted:
            summary += "（已联系兽医）"
        notice = notification_service.create_notification(
            db,
            order.owner_id,
            f"{pet_name}的异常情况已处理",
            summary,
            category="order",
            link="/boarding",
            dedupe_key=f"abnormal:{case.id}:owner:resolved",
        )
    case.owner_notified = bool(case.owner_notified or notice)

    _audit(db, user.id, "abnormal_case.resolve", case.id, before=before, after=_snapshot(case))
    db.commit()
    db.refresh(case)
    return _serialize(db, case)


def reopen(db: Session, user: User, case_id: int) -> dict:
    """管理员把结单撤回到待处置，用于处置错误或情况反复。"""
    if user.role != "admin":
        raise BusinessException(message="只有管理员可以重新打开处置单", code=403)
    case = db.get(BoardingAbnormalCase, case_id)
    if not case:
        raise BusinessException(message="处置单不存在", code=404)
    if case.status != "resolved":
        raise BusinessException(message="只有已完成的处置单可以重新打开", code=409)

    before = _snapshot(case)
    case.status = "open"
    case.handler_id = None
    case.claimed_at = None
    case.resolved_at = None
    case.resolved_by = None
    case.action_taken = None
    case.vet_contacted = False
    _audit(db, user.id, "abnormal_case.reopen", case.id, before=before, after=_snapshot(case))
    db.commit()
    db.refresh(case)
    return _serialize(db, case)


def stats(db: Session) -> dict:
    """管理端概览用：待处置数量与近 30 天平均处置时长（分钟）。"""
    open_count = (
        db.query(BoardingAbnormalCase)
        .filter(BoardingAbnormalCase.status.in_(("open", "processing")))
        .count()
    )
    critical_open = (
        db.query(BoardingAbnormalCase)
        .filter(
            BoardingAbnormalCase.status.in_(("open", "processing")),
            BoardingAbnormalCase.severity == "critical",
        )
        .count()
    )
    rows = (
        db.query(BoardingAbnormalCase.claimed_at, BoardingAbnormalCase.resolved_at)
        .filter(
            BoardingAbnormalCase.status == "resolved",
            BoardingAbnormalCase.resolved_at.is_not(None),
        )
        .order_by(BoardingAbnormalCase.id.desc())
        .limit(200)
        .all()
    )
    durations = [
        (resolved_at - claimed_at).total_seconds() / 60
        for claimed_at, resolved_at in rows
        if claimed_at and resolved_at
    ]
    avg_minutes = round(sum(durations) / len(durations), 1) if durations else None
    return {
        "open": open_count,
        "critical_open": critical_open,
        "resolved_recent": len(rows),
        "avg_resolve_minutes": avg_minutes,
    }
