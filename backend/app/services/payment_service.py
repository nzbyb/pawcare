"""支付单与收银台渠道。

`PAYMENT_PROVIDER` 决定渠道：mock 指向本地支付页，回调由页面上的
「模拟支付成功」触发；alipay 走电脑网站支付，异步通知验签后核销，
并用主动查单兜底。两种渠道共用同一套状态机与订单联动。
"""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder
from app.models.payment import PaymentOrder
from app.models.pet import Pet
from app.models.user import User
from app.payments import alipay
from app.services import notification_service

logger = logging.getLogger(__name__)

PAYABLE_ORDER_STATUSES = ("pending", "confirmed")
ACTIVE_PAYMENT_STATUSES = ("created", "paying")
PROVIDERS = ("mock", "alipay")


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
        "pay_url": payment.pay_url,
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


def _provider() -> str:
    name = (settings.PAYMENT_PROVIDER or "mock").strip().lower()
    if name not in PROVIDERS:
        raise BusinessException(message="支付渠道配置错误", code=503)
    return name


def _alipay_config() -> tuple[str, str, str, str]:
    app_id = settings.ALIPAY_APP_ID.strip()
    private_key = settings.ALIPAY_PRIVATE_KEY.strip()
    public_key = settings.ALIPAY_PUBLIC_KEY.strip()
    if not app_id or not private_key or not public_key:
        raise BusinessException(message="支付宝参数未配置完整，暂时无法支付", code=503)
    return app_id, private_key, public_key, settings.ALIPAY_GATEWAY.strip()


def _notify_url() -> str:
    configured = settings.ALIPAY_NOTIFY_URL.strip()
    if configured:
        return configured
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/payments/alipay/notify"


def _return_url(payment_no: str, token: str) -> str:
    """支付完成后回到前端支付页；token 保留，页面可继续查状态。"""
    return (
        f"{settings.PAYMENT_MOCK_BASE_URL.rstrip('/')}/pay/{payment_no}"
        f"?token={token}"
    )


def _mock_url(payment_no: str, token: str) -> str:
    return (
        f"{settings.PAYMENT_MOCK_BASE_URL.rstrip('/')}/pay/{payment_no}"
        f"?token={token}"
    )


def _amount_text(value: float | Decimal) -> str:
    return f"{Decimal(str(value)):.2f}"


def _alipay_pay_url(
    order: BoardingOrder, payment_no: str, token: str
) -> str:
    app_id, private_key, _public_key, gateway = _alipay_config()
    try:
        return alipay.page_pay_url(
            app_id=app_id,
            private_key=private_key,
            gateway=gateway,
            notify_url=_notify_url(),
            return_url=_return_url(payment_no, token),
            out_trade_no=payment_no,
            amount=_amount_text(order.total_amount),
            subject=f"PawCare 寄养订单 #{order.id}",
            timeout_express=f"{settings.PAYMENT_TTL_MINUTES}m",
        )
    except alipay.AlipayError as exc:
        logger.exception("生成支付宝收银台地址失败")
        raise BusinessException(
            message=f"支付宝暂时不可用：{exc}", code=503
        ) from exc


def _amount_matches(raw: object, expected: float | Decimal) -> bool:
    try:
        return Decimal(str(raw)) == Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return False


def create_payment(db: Session, user: User, order_id: int) -> PaymentOrder:
    now = _now()
    order = _check_payable(db, user, order_id, now)
    channel = _provider()

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
    if existing and existing.channel != channel:
        # 切换支付渠道后旧渠道的单据失效，避免 mock 单混进真实渠道。
        existing.status = "closed"
        db.flush()
        existing = None
    if existing:
        if existing.channel == "alipay":
            # 复用旧支付单时重新签名：收银台 URL 带时间戳，过期后会被网关拒绝。
            existing.pay_url = _alipay_pay_url(
                order, existing.payment_no, existing.qr_token
            )
        db.commit()
        return existing

    token = secrets.token_urlsafe(24)
    for _ in range(5):
        payment_no = _new_payment_no()
        if not db.query(PaymentOrder).filter(PaymentOrder.payment_no == payment_no).first():
            break
    else:
        raise BusinessException(message="支付单生成失败，请重试", code=503)

    pay_url = _mock_url(payment_no, token)
    qr_content = pay_url
    if channel == "alipay":
        pay_url = _alipay_pay_url(order, payment_no, token)
        # 电脑网站支付没有二维码内容，前端按渠道展示「前往支付宝」。
        qr_content = ""

    payment = PaymentOrder(
        payment_no=payment_no,
        order_id=order.id,
        owner_id=order.owner_id,
        channel=channel,
        amount=order.total_amount,
        status="created",
        qr_token=token,
        qr_content=qr_content,
        pay_url=pay_url,
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


def _settle_paid(
    db: Session,
    payment: PaymentOrder,
    *,
    transaction_id: str,
    payload: dict,
) -> None:
    """把支付单核销为 paid，并联动订单、审计与通知。

    幂等：订单已经由另一张支付单付清时，当前支付单关闭而不是重复入账。
    调用方需要先锁定 payment / 校验渠道与金额。
    """
    now = _now()
    order = (
        db.query(BoardingOrder)
        .filter(BoardingOrder.id == payment.order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise BusinessException(message="订单不存在", code=404)

    payment.notify_payload = payload
    if order.payment_status == "paid":
        # 另一张支付单已经收款，当前这张直接关闭，避免重复入账。
        payment.status = "closed"
        db.commit()
        return
    if order.status == "cancelled":
        # 订单已取消却收到付款：沙箱环境先关闭支付单并留审计，真实环境应退款。
        payment.status = "closed"
        db.commit()
        logger.warning(
            "已取消订单收到支付，已关单待人工退款 order=%s payment=%s",
            order.id,
            payment.payment_no,
        )
        return

    payment.status = "paid"
    payment.paid_at = now
    payment.transaction_id = transaction_id
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


def mock_notify(db: Session, payment_no: str, token: str) -> PaymentOrder:
    """模拟渠道回调：校验凭证 → 关闭/核销支付单 → 更新订单 → 写审计。"""
    if _provider() != "mock":
        # 切到真实渠道后，模拟回调必须彻底关闭，否则可以白拿订单。
        raise BusinessException(message="模拟支付已关闭", code=403)

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

    _settle_paid(
        db,
        payment,
        transaction_id=f"MOCK-{payment.payment_no}",
        payload={
            "channel": "mock",
            "payment_no": payment.payment_no,
            "amount": payment.amount,
            "paid_at": now.isoformat(timespec="seconds"),
        },
    )
    return payment


def _notify_payload(form: dict) -> dict:
    keys = (
        "app_id",
        "seller_id",
        "out_trade_no",
        "trade_no",
        "trade_status",
        "total_amount",
        "receipt_amount",
        "gmt_payment",
        "notify_time",
        "notify_type",
        "notify_id",
        "charset",
        "version",
    )
    return {key: form.get(key) for key in keys if form.get(key) not in (None, "")}


def handle_alipay_notify(db: Session, form: dict) -> None:
    """处理支付宝异步通知：验签 → 校验商户与金额 → 走统一核销。"""
    if _provider() != "alipay":
        raise BusinessException(message="支付宝支付未启用", code=403)
    app_id, _private_key, public_key, _gateway = _alipay_config()

    if not alipay.verify_notify(form, public_key):
        raise BusinessException(message="支付宝通知验签失败", code=400)
    if str(form.get("app_id") or "") != app_id:
        raise BusinessException(message="支付宝通知 app_id 不匹配", code=400)
    seller_id = settings.ALIPAY_SELLER_ID.strip()
    if seller_id and str(form.get("seller_id") or "") != seller_id:
        raise BusinessException(message="支付宝通知收款账号不匹配", code=400)

    payment_no = str(form.get("out_trade_no") or "")
    if not payment_no:
        raise BusinessException(message="支付宝通知缺少商户订单号", code=400)

    payment = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment_no)
        .with_for_update()
        .first()
    )
    if not payment:
        raise BusinessException(message="支付单不存在", code=404)
    if payment.channel != "alipay":
        raise BusinessException(message="支付单渠道不匹配", code=400)

    payload = _notify_payload(form)
    trade_status = str(form.get("trade_status") or "")
    if trade_status not in alipay.TRADE_SUCCESS:
        # 未成功只留档，不改订单；返回成功避免支付宝反复通知。
        payment.notify_payload = payload
        db.commit()
        return

    if payment.status == "paid":
        db.commit()
        return
    if not _amount_matches(form.get("total_amount"), payment.amount):
        raise BusinessException(message="支付宝通知金额与支付单不一致", code=400)

    _settle_paid(
        db,
        payment,
        transaction_id=str(form.get("trade_no") or f"ALIPAY-{payment.payment_no}"),
        payload=payload,
    )


def refresh_payment(db: Session, payment: PaymentOrder) -> PaymentOrder:
    """主动向支付宝查单；异步通知丢失时作为兜底。"""
    if payment.channel != "alipay" or payment.status not in ACTIVE_PAYMENT_STATUSES:
        return payment

    app_id, private_key, public_key, gateway = _alipay_config()
    try:
        node = alipay.query_trade(
            app_id=app_id,
            private_key=private_key,
            public_key=public_key,
            gateway=gateway,
            out_trade_no=payment.payment_no,
            timeout=settings.ALIPAY_QUERY_TIMEOUT_SECONDS,
        )
    except alipay.AlipayError:
        # 查单失败不能影响页面展示，交给下次轮询或异步通知。
        logger.warning("支付宝查单失败 payment=%s", payment.payment_no, exc_info=True)
        return payment

    if not node:
        return payment
    if str(node.get("out_trade_no") or "") != payment.payment_no:
        raise BusinessException(message="支付宝查单返回的订单号不匹配", code=400)
    if node.get("trade_status") not in alipay.TRADE_SUCCESS:
        return payment
    if not _amount_matches(node.get("total_amount"), payment.amount):
        raise BusinessException(message="支付宝查单金额与支付单不一致", code=400)

    locked = _get_payment(db, payment.payment_no)
    if locked.status == "paid":
        db.commit()
        return locked
    _settle_paid(
        db,
        locked,
        transaction_id=str(node.get("trade_no") or f"ALIPAY-{locked.payment_no}"),
        payload={"source": "query", **node},
    )
    return locked


def refresh_public_payment(
    db: Session, payment_no: str, token: str
) -> PaymentOrder:
    payment = get_public_payment(db, payment_no, token)
    return refresh_payment(db, payment)
