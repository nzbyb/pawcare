"""MCP 入口治理：审计、限流和管理端查询。"""

import asyncio

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.config import settings
from app.mcp.audit import arguments_payload
from app.mcp.auth import MCPAuthMiddleware
from app.mcp.rate_limit import MCPRateLimiter
from app.mcp.server import execute_read_tool
from app.models.mcp import MCPAuditLog
from app.models.user import User


def _user(db, username: str) -> User:
    return db.query(User).filter(User.username == username).one()


def _latest_audit(db) -> MCPAuditLog:
    db.expire_all()
    return db.query(MCPAuditLog).order_by(MCPAuditLog.id.desc()).first()


def test_audit_records_successful_call(db, owner_credentials):
    user = _user(db, owner_credentials["username"])

    result = execute_read_tool(
        "list_my_pets", {}, user.id, transport="http", ip="203.0.113.9"
    )

    assert result["ok"] is True
    log = _latest_audit(db)
    assert log.user_id == user.id
    assert log.transport == "http"
    assert log.tool_name == "list_my_pets"
    assert log.status == "ok"
    assert log.error_code is None
    assert log.ip == "203.0.113.9"
    assert log.elapsed_ms is not None
    assert log.trace_id and log.trace_id.startswith("mcp-")


def test_audit_records_denied_tool(db, owner_credentials):
    user = _user(db, owner_credentials["username"])

    result = execute_read_tool(
        "create_boarding_draft",
        {"pet_name": "豆豆"},
        user.id,
        transport="stdio",
    )

    assert result["code"] == 403
    log = _latest_audit(db)
    assert log.tool_name == "create_boarding_draft"
    assert log.status == "denied"
    assert log.error_code == "403"
    assert log.transport == "stdio"


def test_audit_can_be_disabled(db, owner_credentials, monkeypatch):
    user = _user(db, owner_credentials["username"])
    monkeypatch.setattr(settings, "MCP_AUDIT_ENABLED", False)

    execute_read_tool("list_my_pets", {}, user.id)

    db.expire_all()
    assert (
        db.query(MCPAuditLog)
        .filter(MCPAuditLog.user_id == user.id)
        .count()
        == 0
    )


def test_arguments_payload_truncates_long_values():
    payload = arguments_payload({"note": "x" * 5000})

    assert payload["truncated"] is True
    assert len(payload["preview"]) == 2000


def test_rate_limiter_blocks_after_limit():
    limiter = MCPRateLimiter(2, storage_uri="")

    assert limiter.check("user:1").allowed is True
    assert limiter.check("user:1").allowed is True
    blocked = limiter.check("user:1")
    assert blocked.allowed is False
    assert blocked.retry_after == 60
    # 不同 key 互不影响。
    assert limiter.check("user:2").allowed is True


def test_rate_limiter_disabled_when_limit_is_zero():
    limiter = MCPRateLimiter(0)

    assert limiter.check("user:1").allowed is True


async def _whoami(request):
    return JSONResponse({"user_id": request.scope["state"]["pawcare_user_id"]})


def test_http_rate_limit_returns_429(db, owner_credentials):
    from app.utils.jwt import create_access_token

    user = _user(db, owner_credentials["username"])
    token = create_access_token(user.id, user.token_version or 0)

    app = MCPAuthMiddleware(
        Starlette(routes=[Route("/mcp", _whoami, methods=["POST"])]),
        rate_limiter=MCPRateLimiter(1, storage_uri=""),
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/mcp", headers=headers).status_code == 200
    blocked = client.post("/mcp", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert blocked.json()["code"] == 429


def test_admin_can_query_mcp_audit(
    client, db, owner_credentials, admin_headers, owner_headers
):
    user = _user(db, owner_credentials["username"])
    execute_read_tool("list_my_pets", {}, user.id, ip="198.51.100.7")

    resp = client.get("/api/admin/mcp-audit", headers=admin_headers)
    body = resp.json()
    assert body["code"] == 200
    item = body["data"]["items"][0]
    assert item["tool_name"] == "list_my_pets"
    assert item["status"] == "ok"
    assert item["ip"] == "198.51.100.7"
    assert item["user_id"] == user.id

    forbidden = client.get("/api/admin/mcp-audit", headers=owner_headers)
    assert forbidden.json()["code"] == 403


def test_mcp_module_does_not_expose_write_tools():
    """守住“对外只读”：FastMCP 实例里不能出现写工具。"""
    from app.mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert "create_boarding_draft" not in names
    assert all(tool.annotations.readOnlyHint for tool in tools)
