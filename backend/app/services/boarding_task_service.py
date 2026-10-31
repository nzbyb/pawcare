"""寄养员今日任务：批量读取订单和当日日报，不改变订单状态。"""

from datetime import date

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.boarding import BoardingDailyReport, BoardingOrder, Kennel
from app.models.pet import Pet
from app.models.user import User


def today_tasks(db: Session, user: User) -> dict:
    if user.role not in ("boarding_staff", "admin"):
        raise BusinessException(message="只有寄养员和管理员可以查看今日任务", code=403)
    today = date.today()
    groups = {key: [] for key in ("pending", "arrivals", "departures", "missing_reports", "abnormal_reports")}
    rows = (
        db.query(BoardingOrder, Pet.name, Kennel.code)
        .join(Pet, BoardingOrder.pet_id == Pet.id)
        .join(Kennel, BoardingOrder.kennel_id == Kennel.id)
        .filter(BoardingOrder.status.in_(("pending", "confirmed", "checked_in", "boarding")))
        .order_by(BoardingOrder.start_date.asc(), BoardingOrder.id.asc())
        .all()
    )
    ids = [order.id for order, _, _ in rows]
    reports = (
        db.query(BoardingDailyReport)
        .filter(BoardingDailyReport.order_id.in_(ids), BoardingDailyReport.report_date == today)
        .all()
    ) if ids else []
    by_order = {report.order_id: report for report in reports}
    for order, pet_name, kennel_code in rows:
        item = {
            "order_id": order.id, "pet_id": order.pet_id, "pet_name": pet_name,
            "kennel_code": kennel_code, "start_date": order.start_date,
            "end_date": order.end_date, "status": order.status,
            "payment_status": order.payment_status,
            "report_id": None, "report_date": None, "abnormal_reasons": [],
        }
        if order.status == "pending" and order.end_date > today:
            groups["pending"].append(item)
        if order.status == "confirmed" and order.start_date <= today < order.end_date:
            groups["arrivals"].append(item)
        staying = order.status in ("checked_in", "boarding")
        if staying and order.end_date <= today:
            groups["departures"].append(item)
        report = by_order.get(order.id)
        if staying and (order.checked_in_at.date() if order.checked_in_at else order.start_date) <= today and report is None:
            groups["missing_reports"].append(item)
        if staying and report:
            reasons = []
            if report.appetite == "poor":
                reasons.append("食欲较差")
            if report.stool in ("soft", "diarrhea"):
                reasons.append("腹泻" if report.stool == "diarrhea" else "便便偏软")
            if report.spirit == "low":
                reasons.append("精神低落")
            if reasons:
                groups["abnormal_reports"].append({
                    **item, "report_id": report.id, "report_date": report.report_date,
                    "abnormal_reasons": reasons,
                })
    return {"date": today, "counts": {key: len(items) for key, items in groups.items()}, **groups}
