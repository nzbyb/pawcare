from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SettingKey = Literal[
    "store_name",
    "service_phone",
    "store_address",
    "business_hours",
    "booking_notice",
]
MAX_SETTING_VALUE = 500

LoginFailureReason = Literal[
    "success", "wrong_password", "no_user", "locked", "disabled"
]


class SettingItem(BaseModel):
    key: SettingKey
    value: str = Field(default="", max_length=MAX_SETTING_VALUE)
    description: str | None = None
    update_time: datetime | None = None


class SettingUpdateItem(BaseModel):
    key: SettingKey
    value: str = Field(default="", max_length=MAX_SETTING_VALUE)


class SettingUpdateRequest(BaseModel):
    """整体保存：前端一次提交所有可见设置项。"""

    items: list[SettingUpdateItem] = Field(min_length=1, max_length=10)


class LoginLogItem(BaseModel):
    id: int
    user_id: int | None = None
    username: str
    nickname: str | None = None
    role: str | None = None
    success: bool
    reason: str
    ip: str | None = None
    user_agent: str | None = None
    create_time: datetime | None = None


class SearchItem(BaseModel):
    type: Literal["pet", "order", "announcement", "knowledge"]
    id: int
    title: str
    subtitle: str | None = None
    url: str


class SearchGroup(BaseModel):
    type: str
    label: str
    items: list[SearchItem]
