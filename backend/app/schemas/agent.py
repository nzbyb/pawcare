from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class ToolEvent(BaseModel):
    name: str
    status: str
    summary: str
    latency_ms: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    trace_id: str
    content: str
    draft: dict | None = None
    tool_events: list[ToolEvent] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    last_message_at: datetime
    create_time: datetime | None = None


class AgentMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tool_calls: list | dict | None = None
    tool_call_id: str | None = None
    token_in: int | None = None
    token_out: int | None = None
    latency_ms: int | None = None
    create_time: datetime | None = None
