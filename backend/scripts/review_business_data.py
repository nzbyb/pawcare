"""只读检查答辩数据的一致性，不删除、不修复、不输出联系方式。

在 backend 目录运行：python scripts/review_business_data.py
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.boarding import BoardingOrder


def review(db):
    rows = db.query(BoardingOrder).order_by(BoardingOrder.id).all()
    issues = []
    active = {"pending", "confirmed", "checked_in", "boarding"}
    for order in rows:
        if order.status in ("checked_in", "boarding", "completed") and (
            order.payment_status != "paid" or order.paid_amount < order.total_amount
        ):
            issues.append({"order_id": order.id, "kind": "stay_without_full_payment"})
        if order.status in ("checked_in", "boarding") and order.end_date < date.today():
            issues.append({"order_id": order.id, "kind": "overdue_stay"})
        if order.status == "cancelled" and order.payment_status == "paid":
            issues.append({"order_id": order.id, "kind": "cancelled_payment_needs_refund_review"})
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            if left.status not in active or right.status not in active:
                continue
            if left.start_date < right.end_date and left.end_date > right.start_date:
                if left.pet_id == right.pet_id or left.kennel_id == right.kennel_id:
                    issues.append({"order_ids": [left.id, right.id], "kind": "overlapping_active_orders"})
    return {"checked_on": date.today().isoformat(), "orders_checked": len(rows), "issues": issues}


if __name__ == "__main__":
    with SessionLocal() as db:
        print(json.dumps(review(db), ensure_ascii=False, indent=2))
