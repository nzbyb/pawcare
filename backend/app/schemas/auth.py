from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.user import BCRYPT_MAX_BYTES, UserResponse, check_password_bytes


class SendCodeRequest(BaseModel):
    channel: Literal["email", "phone"]
    target: str = Field(min_length=3, max_length=120)
    scene: Literal["register", "reset"] = "register"


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
        description="字母、数字、下划线",
    )
    password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)
    nickname: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    code: str = Field(pattern=r"^\d{6}$", description="6 位验证码")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password_bytes(value)

    @model_validator(mode="after")
    def check_contact(self) -> "RegisterRequest":
        if bool(self.email) == bool(self.phone):
            raise ValueError("邮箱和手机号必须且只能填写一个")
        return self

    @property
    def channel(self) -> Literal["email", "phone"]:
        return "email" if self.email else "phone"

    @property
    def target(self) -> str:
        return self.email or self.phone or ""


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


class ResetPasswordRequest(BaseModel):
    channel: Literal["email", "phone"]
    target: str = Field(min_length=3, max_length=120)
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password_bytes(value)
