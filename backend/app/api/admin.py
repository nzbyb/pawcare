from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.user import User
from app.schemas.admin import UserStatusUpdate
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["管理端"])


@router.get("/overview", response_model=Response)
def get_overview(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.overview(db))


@router.get("/statistics", response_model=Response)
def get_statistics(
    days: int = Query(default=30),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.statistics(db, days))


@router.get("/knowledge", response_model=Response)
def list_knowledge(
    keyword: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_knowledge(
            db, keyword=keyword, page=page, page_size=page_size
        )
    )


@router.get("/users", response_model=Response)
def list_users(
    keyword: str | None = Query(default=None, max_length=50),
    role: str | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_users(
            db,
            keyword=keyword,
            role=role,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.put("/users/{user_id}/status", response_model=Response)
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = admin_service.set_user_status(db, current_user, user_id, data.status)
    return Response.success(
        message="账号已启用" if data.status == 1 else "账号已停用",
        data={
            "id": user.id,
            "username": user.username,
            "status": user.status,
        },
    )


@router.get("/kennels/occupancy", response_model=Response)
def get_kennel_occupancy(
    day: date | None = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(data=admin_service.kennel_occupancy(db, day))


@router.get("/mcp-audit", response_model=Response)
def list_mcp_audit(
    user_id: int | None = Query(default=None, ge=1),
    tool: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_mcp_audit(
            db,
            user_id=user_id,
            tool=tool,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/audit-logs", response_model=Response)
def list_audit_logs(
    action: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return Response.success(
        data=admin_service.list_audit_logs(
            db, action=action, page=page, page_size=page_size
        )
    )
