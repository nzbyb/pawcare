from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.content import (
    AnnouncementDetail,
    AnnouncementItem,
    FeedbackCreate,
    FeedbackResponse,
)
from app.services import content_service

router = APIRouter(tags=["公告与反馈"])


@router.get("/announcements", response_model=Response)
def list_announcements(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = content_service.list_announcements(db, current_user, limit=limit)
    return Response.success(
        data={
            "items": [AnnouncementItem(**item).model_dump() for item in data["items"]],
            "unread": data["unread"],
        }
    )


@router.get("/announcements/unread-count", response_model=Response)
def unread_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Response.success(
        data={"unread": content_service.unread_count(db, current_user)}
    )


@router.post("/announcements/read-all", response_model=Response)
def read_all_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = content_service.mark_all_read(db, current_user)
    return Response.success(message=f"已标记 {count} 条公告为已读", data={"unread": 0})


@router.get("/announcements/{announcement_id}", response_model=Response)
def get_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = content_service.get_announcement(db, current_user, announcement_id)
    return Response.success(data=AnnouncementDetail(**data).model_dump())


@router.post("/feedback", response_model=Response)
def create_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = content_service.create_feedback(db, current_user, data)
    return Response.success(
        message="反馈已提交",
        data=FeedbackResponse.model_validate(row).model_dump(),
    )


@router.get("/feedback", response_model=Response)
def list_my_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Response.success(data={"items": content_service.list_my_feedback(db, current_user)})
