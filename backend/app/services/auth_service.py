from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.schemas.user import ChangePasswordRequest, UserResponse
from app.utils.jwt import create_access_token
from app.utils.password import hash_password, verify_password


def register(db: Session, data: RegisterRequest) -> User:
    if db.query(User).filter(User.username == data.username).first():
        raise BusinessException(message="账号已存在")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        nickname=data.nickname or data.username,
        role="pet_owner",
        phone=data.phone,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, data: LoginRequest) -> LoginResponse:
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise BusinessException(message="账号或密码错误")
    if user.status != 1:
        raise BusinessException(message="账号被禁用")

    token = create_access_token(user.id, user.token_version or 0)
    return LoginResponse(token=token, user=UserResponse.model_validate(user))


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
