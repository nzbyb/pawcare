from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import ChangePasswordRequest, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=Response)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(db, data)
    return Response.success(
        message="注册成功", data=UserResponse.model_validate(user).model_dump()
    )


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


@router.put("/password", response_model=Response)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = auth_service.change_password(db, current_user, data)
    return Response.success(message="密码已修改", data={"token": token})
