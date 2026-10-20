from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.payment import MockNotifyRequest, PaymentCreateRequest
from app.services import payment_service

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


# 静态路径必须排在 /{payment_no} 之前，否则 "mock" 会被当成支付单号。
@router.get("/mock/{payment_no}", response_model=Response)
def get_mock_payment(
    payment_no: str,
    token: str = Query(min_length=8, max_length=80),
    db: Session = Depends(get_db),
):
    payment = payment_service.get_public_payment(db, payment_no, token)
    return Response.success(data=payment_service.public_payment_payload(payment))


@router.post("/mock/notify", response_model=Response)
@limiter.limit("30/minute")
def mock_notify(
    request: Request,
    data: MockNotifyRequest,
    db: Session = Depends(get_db),
):
    """模拟渠道的异步回调。真实渠道在这里验签后再复用同一段状态机。"""
    payment = payment_service.mock_notify(db, data.payment_no, data.token)
    return Response.success(
        message="支付成功",
        data=payment_service.public_payment_payload(payment),
    )


@router.get("/{payment_no}", response_model=Response)
def get_payment(
    payment_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = payment_service.get_payment(db, current_user, payment_no)
    return Response.success(data=payment_service.payment_payload(payment))
