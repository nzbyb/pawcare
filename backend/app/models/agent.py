from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JsonType


class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    __table_args__ = {"comment": "Agent 会话"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), default="新对话", nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = {"comment": "Agent 消息"}

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="user / assistant / tool / system"
    )
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_calls: Mapped[dict | None] = mapped_column(JsonType)
    tool_call_id: Mapped[str | None] = mapped_column(String(100))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = {"comment": "Agent 工具调用 trace"}

    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="SET NULL"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="SET NULL"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    arguments: Mapped[dict | None] = mapped_column(JsonType)
    result_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="ok", nullable=False, comment="ok / error"
    )
    error_code: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column()
    token_in: Mapped[int | None] = mapped_column()
    token_out: Mapped[int | None] = mapped_column()
