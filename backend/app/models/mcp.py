from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JsonType


class MCPAuditLog(Base):
    """每一次 MCP 工具调用的审计记录。

    只记录调用元数据和参数摘要，不记录完整业务数据；参数超过 2KB 时
    截断为预览，避免审计表反过来成为数据副本。
    """

    __tablename__ = "mcp_audit_logs"
    __table_args__ = {"comment": "MCP 工具调用审计"}

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    transport: Mapped[str] = mapped_column(String(16), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    arguments: Mapped[dict | None] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(16))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
