from pydantic import BaseModel, Field, field_validator

from app.schemas.user import BCRYPT_MAX_BYTES, UserResponse, check_password_bytes


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
        description="字母、数字、下划线",
    )
    password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)
    nickname: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password_bytes(value)


class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=BCRYPT_MAX_BYTES)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password_bytes(value)


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
