import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.payment import MockNotifyRequest, PaymentCreateRequest
from app.services import payment_service

from app.services import refund_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["支付"])


@router.post("", response_model=Response)
def create_payment(
    data: PaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = payment_service.create_payment(db, current_user, data.order_id)
    return Response.success(
        message="支付单已创建",
        data=payment_service.payment_payload(payment),
    )


@router.post("/alipay/notify", include_in_schema=False)
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    """支付宝异步通知。

    支付宝只认响应体是否为 success，因此这里不套统一 JSON 响应；
    验签或金额校验失败返回 failure，支付宝会按自己的策略重试。
    """
    raw = await request.form()
    form = {key: value for key, value in raw.items() if isinstance(value, str)}
    try:
        payment_service.handle_alipay_notify(db, form)
    except BusinessException as exc:
        logger.warning(
            "支付宝通知处理失败 code=%s message=%s", exc.code, exc.message
        )
        return PlainTextResponse("failure")
    except Exception:
        logger.exception("支付宝通知处理异常")
        return PlainTextResponse("failure")
    return PlainTextResponse("success")


@router.post("/refunds/orders/{order_id}", response_model=Response)
def request_refund(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=refund_service.payload(refund_service.request_refund(db, current_user, order_id)))


@router.post("/refunds/{refund_id}/process", response_model=Response)
def process_refund(refund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return Response.success(data=refund_service.payload(refund_service.process_refund(db, current_user, refund_id)))


# 静态路径必须排在 /{payment_no} 之前，否则 "mock" 会被当成支付单号。
@router.get("/public/{payment_no}", response_model=Response)
def get_public_payment(
    payment_no: str,
    token: str = Query(min_length=8, max_length=80),
    db: Session = Depends(get_db),
):
    payment = payment_service.get_public_payment(db, payment_no, token)
    return Response.success(data=payment_service.public_payment_payload(payment))


@router.post("/public/{payment_no}/refresh", response_model=Response)
@limiter.limit("20/minute")
def refresh_public_payment(
    request: Request,
    payment_no: str,
    token: str = Query(min_length=8, max_length=80),
    db: Session = Depends(get_db),
):
    """支付页回到前台后主动查单，弥补异步通知延迟。"""
    payment = payment_service.refresh_public_payment(db, payment_no, token)
    return Response.success(data=payment_service.public_payment_payload(payment))


@router.get("/mock/{payment_no}", response_model=Response)
def get_mock_payment(
    payment_no: str,
    token: str = Query(min_length=8, max_length=80),
    db: Session = Depends(get_db),
):
    """兼容旧二维码地址；行为与 /public 相同。"""
    payment = payment_service.get_public_payment(db, payment_no, token)
    return Response.success(data=payment_service.public_payment_payload(payment))


@router.post("/mock/notify", response_model=Response)
@limiter.limit("30/minute")
def mock_notify(
    request: Request,
    data: MockNotifyRequest,
    db: Session = Depends(get_db),
):
    """模拟渠道的异步回调；切到 alipay 后会被服务层拒绝。"""
    payment = payment_service.mock_notify(db, data.payment_no, data.token)
    return Response.success(
        message="支付成功",
        data=payment_service.public_payment_payload(payment),
    )


@router.post("/{payment_no}/refresh", response_model=Response)
def refresh_payment(
    payment_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = payment_service.get_payment(db, current_user, payment_no)
    payment = payment_service.refresh_payment(db, payment)
    return Response.success(data=payment_service.payment_payload(payment))


@router.get("/{payment_no}", response_model=Response)
def get_payment(
    payment_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = payment_service.get_payment(db, current_user, payment_no)
    return Response.success(data=payment_service.payment_payload(payment))
