from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnnouncementCategory = Literal["notice", "policy", "activity"]
AnnouncementAudience = Literal["all", "pet_owner", "boarding_staff", "admin"]
AnnouncementStatus = Literal["draft", "published", "archived"]
FeedbackCategory = Literal["bug", "suggestion", "service", "other"]
FeedbackStatus = Literal["pending", "processing", "resolved", "closed"]


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    category: AnnouncementCategory = "notice"
    content: str = Field(min_length=2, max_length=5000)
    audience: AnnouncementAudience = "all"
    status: AnnouncementStatus = "draft"
    is_pinned: bool = False
    attachment_url: str | None = Field(default=None, max_length=255)
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class AnnouncementUpdate(AnnouncementCreate):
    pass


class AnnouncementItem(BaseModel):
    """列表卡片：不带正文，避免一次拉全部内容。"""

    id: int
    title: str
    category: str
    audience: str
    is_pinned: bool
    attachment_url: str | None = None
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    create_time: datetime | None = None
    is_read: bool = False
    read_count: int | None = None


class AnnouncementDetail(AnnouncementItem):
    content: str
    status: str
    is_read: bool = True


class AnnouncementReadUser(BaseModel):
    user_id: int
    username: str
    nickname: str | None = None
    role: str
    read_at: datetime


class FeedbackCreate(BaseModel):
    category: FeedbackCategory = "suggestion"
    content: str = Field(min_length=5, max_length=1000)
    contact: str | None = Field(default=None, max_length=100)


class FeedbackReply(BaseModel):
    status: FeedbackStatus
    reply: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: str
    content: str
    contact: str | None = None
    status: str
    reply: str | None = None
    replied_at: datetime | None = None
    create_time: datetime | None = None
    username: str | None = None
    nickname: str | None = None
