from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
)
from app.schemas.user import (
    ChangePasswordRequest,
    NotificationPrefsUpdate,
    ProfileUpdate,
    UserResponse,
)
from app.services import auth_service, verification_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/verification-code", response_model=Response)
@limiter.limit("6/minute")
def send_verification_code(
    request: Request, data: SendCodeRequest, db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else None
    payload = verification_service.issue_code(
        db, data.channel, data.target, data.scene, ip
    )
    return Response.success(message="验证码已发送", data=payload)


@router.post("/register", response_model=Response)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(db, data)
    return Response.success(
        message="注册成功", data=UserResponse.model_validate(user).model_dump()
    )


@router.post("/password/reset", response_model=Response)
@limiter.limit("6/minute")
def reset_password(
    request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)
):
    username = auth_service.reset_password(db, data)
    return Response.success(message="密码已重置", data={"username": username})


@router.post("/login", response_model=Response)
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login(db, data)
    return Response.success(message="登录成功", data=result.model_dump())


@router.get("/me", response_model=Response)
def me(current_user: User = Depends(get_current_user)):
    return Response.success(
        data=UserResponse.model_validate(current_user).model_dump()
    )


@router.put("/me", response_model=Response)
def update_me(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = auth_service.update_profile(db, current_user, data)
    return Response.success(
        message="资料已更新", data=UserResponse.model_validate(user).model_dump()
    )


@router.put("/notification-prefs", response_model=Response)
def update_notification_prefs(
    data: NotificationPrefsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = auth_service.update_notification_prefs(db, current_user, data)
    return Response.success(
        message="通知偏好已保存", data=UserResponse.model_validate(user).model_dump()
    )


@router.put("/password", response_model=Response)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = auth_service.change_password(db, current_user, data)
    return Response.success(message="密码已修改", data={"token": token})
