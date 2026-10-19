from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def create_access_token(user_id: int, token_version: int) -> str:
    """签发令牌，`ver` 与 users.token_version 对比，改密码后旧令牌全废。"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"user_id": user_id, "ver": token_version, "exp": expire}
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
