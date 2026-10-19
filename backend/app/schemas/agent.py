from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class DraftConfirmRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
