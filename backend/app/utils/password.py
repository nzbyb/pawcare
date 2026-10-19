import bcrypt

from app.common.exceptions import BusinessException

_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise BusinessException(
            message=f"密码最多 {_BCRYPT_MAX_BYTES} 字节（一个汉字算 3 字节）"
        )
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_to_bcrypt_bytes(password), hashed_password.encode("utf-8"))
