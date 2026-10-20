import math
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user import ChangePasswordRequest, UserResponse
from app.services import verification_service
from app.utils.jwt import create_access_token
from app.utils.password import hash_password, verify_password


def register(db: Session, data: RegisterRequest) -> User:
    channel = data.channel
    target = verification_service.normalize_target(channel, data.target)

    if db.query(User).filter(User.username == data.username).first():
        raise BusinessException(message="账号已存在")
    if channel == "email" and db.query(User).filter(User.email == target).first():
        raise BusinessException(message="该邮箱已被注册")
    if channel == "phone" and db.query(User).filter(User.phone == target).first():
        raise BusinessException(message="该手机号已被注册")

    # 先查重再核销，避免用户名冲突白白消耗一次验证码。
    verification_service.verify_code(db, channel, target, "register", data.code)

    now = datetime.now()
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        nickname=data.nickname or data.username,
        role="pet_owner",
        email=target if channel == "email" else None,
        phone=target if channel == "phone" else None,
        email_verified_at=now if channel == "email" else None,
        phone_verified_at=now if channel == "phone" else None,
        status=1,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 并发注册时唯一索引兜底。
        db.rollback()
        raise BusinessException(message="账号、邮箱或手机号已被注册")
    db.refresh(user)
    return user


def _lock_remaining_minutes(user: User, now: datetime) -> int:
    if not user.locked_until or user.locked_until <= now:
        return 0
    return max(1, math.ceil((user.locked_until - now).total_seconds() / 60))


def _record_login_failure(db: Session, user: User) -> None:
    now = datetime.now()
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= settings.LOGIN_MAX_FAILURES:
        user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        user.failed_login_count = 0
    db.commit()


def login(db: Session, data: LoginRequest) -> LoginResponse:
    user = db.query(User).filter(User.username == data.username).first()
    now = datetime.now()

    if user:
        remaining = _lock_remaining_minutes(user, now)
        if remaining:
            raise BusinessException(
                message=f"账号已锁定，请 {remaining} 分钟后重试", code=429
            )

    if not user or not verify_password(data.password, user.password_hash):
        if user:
            _record_login_failure(db, user)
            if user.locked_until and user.locked_until > now:
                raise BusinessException(
                    message=(
                        f"密码错误次数过多，账号已锁定 "
                        f"{settings.LOGIN_LOCK_MINUTES} 分钟"
                    ),
                    code=429,
                )
        raise BusinessException(message="账号或密码错误")
    if user.status != 1:
        raise BusinessException(message="账号被禁用")

    if user.failed_login_count or user.locked_until:
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()

    token = create_access_token(user.id, user.token_version or 0)
    return LoginResponse(token=token, user=UserResponse.model_validate(user))


def reset_password(db: Session, data: ResetPasswordRequest) -> str:
    target = verification_service.normalize_target(data.channel, data.target)
    verification_service.verify_code(db, data.channel, target, "reset", data.code)

    if data.channel == "email":
        user = db.query(User).filter(User.email == target).first()
    else:
        user = db.query(User).filter(User.phone == target).first()
    if not user:
        raise BusinessException(message="该联系方式尚未注册")

    user.password_hash = hash_password(data.new_password)
    # 旧令牌全部失效，并解除登录锁定。
    user.token_version = (user.token_version or 0) + 1
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return user.username


def change_password(
    db: Session, user: User, data: ChangePasswordRequest
) -> str:
    if not verify_password(data.old_password, user.password_hash):
        raise BusinessException(message="原密码错误")

    user.password_hash = hash_password(data.new_password)
    # 令牌版本 +1：此前签发的令牌全部失效
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return create_access_token(user.id, user.token_version)
