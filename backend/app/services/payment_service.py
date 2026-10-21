"""支付单与模拟收银台。

当前只实现 mock 渠道：二维码指向本地支付页，回调由页面上的
「模拟支付成功」触发。接入支付宝 / 微信时新增 provider，保持
状态机与订单联动不变。
"""

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder
from app.models.payment import PaymentOrder
from app.models.pet import Pet
from app.models.user import User
from app.services import notification_service

PAYABLE_ORDER_STATUSES = ("pending", "confirmed")
ACTIVE_PAYMENT_STATUSES = ("created", "paying")


def _audit(
    db: Session,
    actor_id: int | None,
    action: str,
    target_id: int | None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type="payment_order",
            target_id=target_id,
            after_data=after,
        )
    )


def _now() -> datetime:
    return datetime.now()


def _new_payment_no() -> str:
    return f"PAY{_now():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"


def _close_expired(db: Session, order_id: int, now: datetime) -> None:
    """把已到期的支付单标记为关闭；幂等，可在查询时顺手执行。"""
    db.query(PaymentOrder).filter(
        PaymentOrder.order_id == order_id,
        PaymentOrder.status.in_(ACTIVE_PAYMENT_STATUSES),
        PaymentOrder.expires_at <= now,
    ).update({PaymentOrder.status: "closed"}, synchronize_session=False)


def public_payment_payload(payment: PaymentOrder) -> dict:
    return {
        "payment_no": payment.payment_no,
        "order_id": payment.order_id,
        "channel": payment.channel,
        "amount": payment.amount,
        "status": payment.status,
        "qr_content": payment.qr_content,
        "expires_at": payment.expires_at,
    }


def payment_payload(payment: PaymentOrder) -> dict:
    payload = public_payment_payload(payment)
    payload.update(
        {
            "owner_id": payment.owner_id,
            "paid_at": payment.paid_at,
            "transaction_id": payment.transaction_id,
            "create_time": payment.create_time,
        }
    )
    return payload


def _check_payable(db: Session, user: User, order_id: int, now: datetime) -> BoardingOrder:
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在")
    if order.owner_id != user.id and user.role != "admin":
        raise BusinessException(message="无权支付该订单", code=403)
    if order.status not in PAYABLE_ORDER_STATUSES:
        raise BusinessException(message="当前订单状态不能支付", code=409)
    if order.payment_status == "paid":
        raise BusinessException(message="订单已支付，请勿重复付款", code=409)
    if order.total_amount <= 0:
        raise BusinessException(message="订单金额异常，无法发起支付")

    _close_expired(db, order.id, now)
    return order


def create_payment(db: Session, user: User, order_id: int) -> PaymentOrder:
    now = _now()
    order = _check_payable(db, user, order_id, now)

    # 同一订单未过期的支付单直接复用，避免用户连点生成多张码。
    existing = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.order_id == order.id,
            PaymentOrder.status.in_(ACTIVE_PAYMENT_STATUSES),
            PaymentOrder.expires_at > now,
        )
        .order_by(PaymentOrder.id.desc())
        .first()
    )
    if existing:
        db.commit()
        return existing

    token = secrets.token_urlsafe(24)
    for _ in range(5):
        payment_no = _new_payment_no()
        if not db.query(PaymentOrder).filter(PaymentOrder.payment_no == payment_no).first():
            break
    else:
        raise BusinessException(message="支付单生成失败，请重试", code=503)

    payment = PaymentOrder(
        payment_no=payment_no,
        order_id=order.id,
        owner_id=order.owner_id,
        channel="mock",
        amount=order.total_amount,
        status="created",
        qr_token=token,
        qr_content=(
            f"{settings.PAYMENT_MOCK_BASE_URL.rstrip('/')}/pay/{payment_no}"
            f"?token={token}"
        ),
        expires_at=now + timedelta(minutes=settings.PAYMENT_TTL_MINUTES),
    )
    db.add(payment)
    db.flush()
    _audit(db, user.id, "payment.create", payment.id, {"order_id": order.id})
    db.commit()
    db.refresh(payment)
    return payment


def _get_payment(db: Session, payment_no: str) -> PaymentOrder:
    payment = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment_no)
        .with_for_update()
        .first()
    )
    if not payment:
        raise BusinessException(message="支付单不存在", code=404)
    return payment


def get_payment(db: Session, user: User, payment_no: str) -> PaymentOrder:
    payment = db.query(PaymentOrder).filter(PaymentOrder.payment_no == payment_no).first()
    if not payment:
        raise BusinessException(message="支付单不存在", code=404)
    if payment.owner_id != user.id and user.role != "admin":
        raise BusinessException(message="无权查看该支付单", code=403)

    now = _now()
    if payment.status in ACTIVE_PAYMENT_STATUSES and payment.expires_at <= now:
        payment.status = "closed"
        db.commit()
    return payment


def get_public_payment(db: Session, payment_no: str, token: str) -> PaymentOrder:
    """扫码后打开支付页时的查询；token 只存在于二维码里。"""
    payment = db.query(PaymentOrder).filter(PaymentOrder.payment_no == payment_no).first()
    if not payment:
        raise BusinessException(message="支付单不存在", code=404)
    if not hmac.compare_digest(payment.qr_token, token or ""):
        raise BusinessException(message="支付凭证无效", code=403)

    now = _now()
    if payment.status in ACTIVE_PAYMENT_STATUSES:
        if payment.expires_at <= now:
            payment.status = "closed"
            db.commit()
        elif payment.status == "created":
            payment.status = "paying"
            db.commit()
    return payment


def mock_notify(db: Session, payment_no: str, token: str) -> PaymentOrder:
    """模拟渠道回调：校验凭证 → 关闭/核销支付单 → 更新订单 → 写审计。"""
    payment = _get_payment(db, payment_no)
    if not hmac.compare_digest(payment.qr_token, token or ""):
        raise BusinessException(message="支付凭证无效", code=403)

    if payment.status == "paid":
        db.commit()
        return payment

    now = _now()
    if payment.expires_at <= now:
        payment.status = "closed"
        db.commit()
        raise BusinessException(message="支付单已过期，请重新发起支付", code=409)
    if payment.status not in ACTIVE_PAYMENT_STATUSES:
        raise BusinessException(message="支付单已关闭", code=409)

    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == payment.order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在", code=404)
    if order.payment_status == "paid":
        # 另一张支付单已经收款，当前这张直接关闭，避免重复入账。
        payment.status = "closed"
        db.commit()
        raise BusinessException(message="订单已支付，请勿重复付款", code=409)

    payment.status = "paid"
    payment.paid_at = now
    payment.transaction_id = f"MOCK-{payment.payment_no}"
    payment.notify_payload = {
        "channel": "mock",
        "payment_no": payment.payment_no,
        "amount": payment.amount,
        "paid_at": now.isoformat(timespec="seconds"),
    }
    order.payment_status = "paid"
    order.paid_amount = payment.amount
    _audit(
        db,
        payment.owner_id,
        "payment.paid",
        payment.id,
        {"order_id": order.id, "amount": payment.amount},
    )
    pet = db.get(Pet, order.pet_id)
    pet_name = pet.name if pet else "宠物"
    notification_service.create_notification(
        db,
        payment.owner_id,
        "支付成功",
        f"{pet_name} 的寄养订单已支付 ¥{float(payment.amount):.2f}，预约正式生效。",
        category="order",
        link="/boarding",
        dedupe_key=f"order:{order.id}:paid",
    )
    db.commit()
    db.refresh(payment)
    return payment
