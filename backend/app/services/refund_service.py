"""全额退款：取消后申请，管理员审核执行，渠道成功后才更新订单。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder
from app.models.payment import PaymentOrder
from app.models.refund import RefundOrder
from app.models.user import User
from app.payments import alipay
from app.services import notification_service


def payload(refund: RefundOrder) -> dict:
    return {key: getattr(refund, key) for key in (
        "id", "refund_no", "order_id", "amount", "status", "reason",
        "reviewed_by", "create_time", "completed_at", "error",
    )}


def enqueue(db: Session, order: BoardingOrder, payment: PaymentOrder, reason: str) -> RefundOrder:
    """调用方持有订单锁；与取消或收款使用同一事务，不在这里提交。"""
    existing = db.query(RefundOrder).filter(RefundOrder.payment_id == payment.id).first()
    if existing:
        return existing
    refund = RefundOrder(
        refund_no=f"RF{uuid4().hex}", payment_id=payment.id,
        order_id=order.id, owner_id=order.owner_id, amount=payment.amount,
        status="requested", reason=reason,
    )
    db.add(refund)
    db.flush()
    db.add(AuditLog(actor_id=order.owner_id, action="refund.request", target_type="refund_order",
                    target_id=refund.id, after_data={"order_id": order.id, "amount": float(refund.amount)}))
    notification_service.notify_roles(
        db, ("admin",), "退款待审核", f"订单 #{order.id} 申请全额退款 ¥{float(refund.amount):.2f}。",
        category="order", link="/boarding", dedupe_key=f"refund:{refund.id}:requested",
    )
    return refund


def request_refund(db: Session, user: User, order_id: int) -> RefundOrder:
    if user.role not in ("pet_owner", "admin"):
        raise BusinessException(message="无权申请退款", code=403)
    order = db.query(BoardingOrder).filter(BoardingOrder.id == order_id).with_for_update().first()
    if not order:
        raise BusinessException(message="订单不存在", code=404)
    if user.role != "admin" and order.owner_id != user.id:
        raise BusinessException(message="无权操作该订单", code=403)
    if order.status != "cancelled":
        raise BusinessException(message="请先取消未入住的订单，再申请退款", code=409)
    payment = (db.query(PaymentOrder).filter(PaymentOrder.order_id == order.id, PaymentOrder.status == "paid")
               .order_by(PaymentOrder.id).first())
    if not payment:
        raise BusinessException(message="未找到成功支付记录，请联系管理员核对", code=409)
    refund = enqueue(db, order, payment, "已取消订单申请全额退款")
    db.commit()
    return refund


def process_refund(db: Session, admin: User, refund_id: int) -> RefundOrder:
    if admin.role != "admin":
        raise BusinessException(message="只有管理员可以审核退款", code=403)
    refund = db.query(RefundOrder).filter(RefundOrder.id == refund_id).with_for_update().first()
    if not refund:
        raise BusinessException(message="退款申请不存在", code=404)
    if refund.status == "succeeded":
        return refund
    payment = db.get(PaymentOrder, refund.payment_id)
    order = db.get(BoardingOrder, refund.order_id)
    if not order or order.status != "cancelled" or not payment or payment.status != "paid":
        raise BusinessException(message="订单或支付状态异常，请先核对", code=409)
    if float(refund.amount) != float(payment.amount) or refund.amount <= 0:
        raise BusinessException(message="退款金额与原支付不一致", code=409)
    refund.status = "processing"
    refund.reviewed_by = admin.id
    refund.error = None
    db.commit()

    # 网络超时后使用同一退款号重试；支付宝据此保证不会重复出款。
    try:
        if payment.channel == "alipay":
            from app.services.payment_service import _alipay_config
            from app.config import settings
            app_id, private_key, public_key, gateway = _alipay_config()
            alipay.refund_trade(
                app_id=app_id, private_key=private_key, public_key=public_key, gateway=gateway,
                out_trade_no=payment.payment_no, out_request_no=refund.refund_no,
                amount=f"{refund.amount:.2f}", timeout=settings.ALIPAY_QUERY_TIMEOUT_SECONDS,
            )
        elif payment.channel != "mock":
            raise BusinessException(message="该支付渠道暂不支持自动退款", code=409)
    except (alipay.AlipayError, BusinessException):
        refund = db.query(RefundOrder).filter(RefundOrder.id == refund_id).populate_existing().with_for_update().one()
        if refund.status != "succeeded":
            refund.status = "failed"
            refund.error = "渠道尚未确认退款成功，请核对渠道后使用原退款号重试。"
            db.add(AuditLog(actor_id=admin.id, action="refund.failed", target_type="refund_order", target_id=refund.id))
            db.commit()
        return refund

    refund = db.query(RefundOrder).filter(RefundOrder.id == refund_id).populate_existing().with_for_update().one()
    if refund.status == "succeeded":
        return refund
    refund.status = "succeeded"
    refund.error = None
    refund.completed_at = datetime.now()
    order = db.query(BoardingOrder).filter(BoardingOrder.id == refund.order_id).populate_existing().with_for_update().one()
    order.payment_status = "refunded"
    # paid_amount 保留原实收；净收款由实收减成功退款统计，避免丢失账务历史。
    db.add(AuditLog(actor_id=admin.id, action="refund.succeeded", target_type="refund_order", target_id=refund.id,
                    after_data={"order_id": order.id, "amount": float(refund.amount), "channel": payment.channel}))
    notification_service.create_notification(
        db, order.owner_id, "退款已完成", f"订单 #{order.id} 已原路退回 ¥{float(refund.amount):.2f}。",
        category="order", link=f"/boarding?order={order.id}", dedupe_key=f"refund:{refund.id}:succeeded",
    )
    db.commit()
    return refund
