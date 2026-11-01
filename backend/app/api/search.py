from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.services import search_service

router = APIRouter(prefix="/search", tags=["站内搜索"])


@router.get("", response_model=Response)
@limiter.limit("30/minute")
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """跨宠物、订单、公告的分组搜索，结果按当前用户权限过滤。"""
    return Response.success(
        data=search_service.search(db, current_user, q, limit)
    )
