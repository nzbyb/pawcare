from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

BCRYPT_MAX_BYTES = 72


def check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"密码最多 {BCRYPT_MAX_BYTES} 字节（一个汉字算 3 字节）")
    return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    role: str
    phone: str | None = None
    status: int
    create_time: datetime | None = None


class UserUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(max_length=BCRYPT_MAX_BYTES)
    new_password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("old_password", "new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password_bytes(value)
