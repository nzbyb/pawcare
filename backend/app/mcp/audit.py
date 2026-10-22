"""MCP 调用审计。

记录“谁、通过什么传输、调用了哪个工具、参数摘要、结果状态、耗时”。
审计失败不能影响工具返回：写库异常只记日志并回滚。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.mcp import MCPAuditLog

logger = logging.getLogger(__name__)

MAX_ARGUMENT_CHARS = 2000
DENIED_CODES = {401, 403}


def audit_enabled() -> bool:
    return bool(settings.MCP_AUDIT_ENABLED)


def arguments_payload(arguments: Any) -> dict | None:
    """参数超过 2KB 时只存预览，避免审计表变成业务数据副本。"""
    if arguments is None:
        return None
    if not isinstance(arguments, dict):
        return {"value": str(arguments)[:MAX_ARGUMENT_CHARS]}
    try:
        encoded = json.dumps(arguments, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"preview": str(arguments)[:MAX_ARGUMENT_CHARS]}
    if len(encoded) <= MAX_ARGUMENT_CHARS:
        return arguments
    return {"preview": encoded[:MAX_ARGUMENT_CHARS], "truncated": True}


def _status(result: dict, allowed: bool) -> tuple[str, str | None]:
    if result.get("ok"):
        return "ok", None
    code = result.get("code")
    if code == 504:
        return "timeout", "504"
    if not allowed or code in DENIED_CODES:
        return "denied", str(code or 403)
    return "error", str(code or "")[:16] or None


def _add(
    db: Session,
    *,
    user_id: int | None,
    transport: str,
    tool_name: str,
    arguments: dict | None,
    status: str,
    error_code: str | None,
    elapsed_ms: int | None,
    ip: str | None,
    trace_id: str | None,
) -> None:
    db.add(
        MCPAuditLog(
            user_id=user_id,
            transport=transport,
            tool_name=tool_name[:64],
            arguments=arguments_payload(arguments),
            status=status,
            error_code=error_code,
            elapsed_ms=elapsed_ms,
            ip=ip,
            trace_id=trace_id,
        )
    )


def record(
    db: Session,
    *,
    user_id: int | None,
    transport: str,
    tool_name: str,
    arguments: dict | None,
    result: dict,
    elapsed_ms: int,
    ip: str | None = None,
    trace_id: str | None = None,
    allowed: bool = True,
) -> None:
    """在调用方的事务里写一条审计并立即提交。"""
    if not audit_enabled():
        return
    status, error_code = _status(result, allowed)
    _add(
        db,
        user_id=user_id,
        transport=transport,
        tool_name=tool_name,
        arguments=arguments,
        status=status,
        error_code=error_code,
        elapsed_ms=elapsed_ms,
        ip=ip,
        trace_id=trace_id,
    )
    try:
        db.commit()
    except Exception as exc:
        # 审计是旁路：表未迁移或数据库抖动时只记一条警告，不影响工具返回。
        logger.warning("写入 MCP 审计失败 tool=%s error=%s", tool_name, exc)
        db.rollback()


def record_denied(
    *,
    user_id: int | None,
    transport: str,
    tool_name: str,
    arguments: dict | None,
    code: int,
    ip: str | None = None,
    trace_id: str | None = None,
) -> None:
    """在打开业务会话之前就被拒绝的调用（未开放工具、身份失效）。"""
    if not audit_enabled():
        return
    try:
        with SessionLocal() as db:
            _add(
                db,
                user_id=user_id,
                transport=transport,
                tool_name=tool_name,
                arguments=arguments,
                status="denied",
                error_code=str(code),
                elapsed_ms=None,
                ip=ip,
                trace_id=trace_id,
            )
            db.commit()
    except Exception as exc:
        logger.warning(
            "写入 MCP 拒绝审计失败 tool=%s error=%s", tool_name, exc
        )
