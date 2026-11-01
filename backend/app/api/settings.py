from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import setting_service

router = APIRouter(tags=["系统设置"])


@router.get("/settings", response_model=Response)
def get_public_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """门店信息等公开设置，登录后即可读取（帮助与反馈页使用）。"""
    return Response.success(data=setting_service.public_settings(db))
