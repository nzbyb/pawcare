from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user, require_roles
from app.models.user import User
from app.schemas.boarding import (
    BoardingDraftCreate,
    BoardingHealthCheck,
    BoardingTasks,
    DailyReportCreate,
    DailyReportResponse,
    DraftConfirmRequest,
    KennelCreate,
    KennelResponse,
    KennelSize,
    KennelUpdate,
)
from app.services import boarding_health_service, boarding_service, boarding_task_service

router = APIRouter(tags=["寄养"])


@router.get("/boarding/health-check", response_model=Response)
def get_boarding_health_check(
    pet_id: int = Query(..., gt=0),
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Response.success(data=BoardingHealthCheck.model_validate(
        boarding_health_service.check_health(db, current_user, pet_id, start_date, end_date)
    ).model_dump())


@router.get("/boarding/tasks/today", response_model=Response)
def get_boarding_tasks(
    current_user: User = Depends(require_roles("boarding_staff", "admin")),
    db: Session = Depends(get_db),
):
    return Response.success(data=BoardingTasks.model_validate(
        boarding_task_service.today_tasks(db, current_user)
    ).model_dump())


@router.get("/kennels", response_model=Response)
def list_kennels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kennels = boarding_service.list_kennels(db)
    return Response.success(
        data=[KennelResponse.model_validate(item).model_dump() for item in kennels]
    )


@router.get("/kennels/availability", response_model=Response)
def check_kennel_availability(
    start_date: date = Query(...),
    end_date: date = Query(...),
    size: KennelSize | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kennels = boarding_service.check_availability(db, start_date, end_date, size)
    return Response.success(
        data=[KennelResponse.model_validate(item).model_dump() for item in kennels]
    )


@router.post("/kennels", response_model=Response)
def create_kennel(
    data: KennelCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    kennel = boarding_service.create_kennel(db, current_user, data)
    return Response.success(
        message="笼舍已创建",
        data=KennelResponse.model_validate(kennel).model_dump(),
    )


@router.put("/kennels/{kennel_id}", response_model=Response)
def update_kennel(
    kennel_id: int,
    data: KennelUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    kennel = boarding_service.update_kennel(db, current_user, kennel_id, data)
    return Response.success(
        message="笼舍已更新",
        data=KennelResponse.model_validate(kennel).model_dump(),
    )


@router.post("/boarding/drafts", response_model=Response)
def create_boarding_draft(
    data: BoardingDraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draft = boarding_service.create_draft(db, current_user, data)
    return Response.success(
        message="预约草稿已生成，请在 15 分钟内确认",
        data=boarding_service.draft_payload(db, draft),
    )


@router.get("/boarding/drafts", response_model=Response)
def list_boarding_drafts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drafts = boarding_service.list_drafts(db, current_user)
    return Response.success(
        data=[boarding_service.draft_payload(db, item) for item in drafts]
    )


@router.get("/boarding/drafts/{draft_id}", response_model=Response)
def get_boarding_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draft = boarding_service.get_draft(db, current_user, draft_id)
    return Response.success(data=boarding_service.draft_payload(db, draft))


@router.post("/boarding/drafts/{draft_id}/confirm", response_model=Response)
def confirm_boarding_draft(
    draft_id: int,
    data: DraftConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = boarding_service.confirm_draft(
        db, current_user, draft_id, data.idempotency_key
    )
    return Response.success(
        message="预约已确认，等待寄养员接单",
        data=boarding_service.order_payload(db, order),
    )


@router.delete("/boarding/drafts/{draft_id}", response_model=Response)
def cancel_boarding_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boarding_service.cancel_draft(db, current_user, draft_id)
    return Response.success(message="草稿已取消")


@router.get("/boarding/orders", response_model=Response)
def list_boarding_orders(
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = boarding_service.list_orders(db, current_user, status)
    return Response.success(
        data=[boarding_service.order_payload(db, item) for item in orders]
    )


@router.get("/boarding/orders/{order_id}", response_model=Response)
def get_boarding_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = boarding_service.get_order(db, current_user, order_id)
    return Response.success(data=boarding_service.order_payload(db, order))


@router.get("/boarding/orders/{order_id}/handover", response_model=Response)
def get_boarding_handover(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=boarding_service.handover_payload(db, current_user, order_id)
    )


@router.post("/boarding/orders/{order_id}/confirm", response_model=Response)
def confirm_boarding_order(
    order_id: int,
    current_user: User = Depends(require_roles("boarding_staff", "admin")),
    db: Session = Depends(get_db),
):
    order = boarding_service.confirm_order(db, current_user, order_id)
    return Response.success(
        message="订单已确认",
        data=boarding_service.order_payload(db, order),
    )


@router.post("/boarding/orders/{order_id}/check-in", response_model=Response)
def check_in_boarding_order(
    order_id: int,
    current_user: User = Depends(require_roles("boarding_staff", "admin")),
    db: Session = Depends(get_db),
):
    order = boarding_service.check_in(db, current_user, order_id)
    return Response.success(
        message="已办理入住",
        data=boarding_service.order_payload(db, order),
    )


@router.post("/boarding/orders/{order_id}/check-out", response_model=Response)
def check_out_boarding_order(
    order_id: int,
    current_user: User = Depends(require_roles("boarding_staff", "admin")),
    db: Session = Depends(get_db),
):
    order = boarding_service.check_out(db, current_user, order_id)
    return Response.success(
        message="已办理退房",
        data=boarding_service.order_payload(db, order),
    )


@router.post("/boarding/orders/{order_id}/cancel", response_model=Response)
def cancel_boarding_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = boarding_service.cancel_order(db, current_user, order_id)
    return Response.success(
        message="订单已取消",
        data=boarding_service.order_payload(db, order),
    )


@router.post("/boarding/orders/{order_id}/reports", response_model=Response)
def create_daily_report(
    order_id: int,
    data: DailyReportCreate,
    current_user: User = Depends(require_roles("boarding_staff", "admin")),
    db: Session = Depends(get_db),
):
    report = boarding_service.add_daily_report(db, current_user, order_id, data)
    return Response.success(
        message="日报已保存",
        data=DailyReportResponse.model_validate(report).model_dump(),
    )


@router.get("/boarding/orders/{order_id}/reports", response_model=Response)
def list_daily_reports(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = boarding_service.list_daily_reports(db, current_user, order_id)
    return Response.success(
        data=[DailyReportResponse.model_validate(item).model_dump() for item in reports]
    )
