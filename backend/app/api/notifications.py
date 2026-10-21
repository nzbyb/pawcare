from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services import notification_service

router = APIRouter(tags=["站内通知"])


@router.get("/notifications", response_model=Response)
def list_notifications(
    limit: int = Query(default=10, ge=1, le=50),
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 没有常驻调度器，打开通知列表时顺手补齐到期的健康提醒。
    notification_service.sync_due_reminders(db, current_user)
    items = notification_service.list_notifications(
        db, current_user, limit=limit, unread_only=unread_only
    )
    return Response.success(
        data={
            "items": [
                NotificationResponse.model_validate(item).model_dump()
                for item in items
            ],
            "unread": notification_service.unread_count(db, current_user),
        }
    )


@router.get("/notifications/unread-count", response_model=Response)
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification_service.sync_due_reminders(db, current_user)
    return Response.success(
        data={"unread": notification_service.unread_count(db, current_user)}
    )


@router.post("/notifications/{notification_id}/read", response_model=Response)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unread = notification_service.mark_read(db, current_user, notification_id)
    return Response.success(data={"unread": unread})


@router.post("/notifications/read-all", response_model=Response)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification_service.mark_all_read(db, current_user)
    return Response.success(message="已全部标记为已读", data={"unread": 0})
