"""MCP Server：协议暴露面、身份隔离和只读边界。"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.agent.tools import TOOL_DEFINITIONS
from app.mcp.auth import MCPAuthMiddleware
from app.mcp.server import READ_ONLY_TOOLS, execute_read_tool, mcp
from app.models.pet import Pet
from app.models.user import User
from app.utils.jwt import create_access_token
from app.utils.password import hash_password
from tests.conftest import unique_username

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _user(db, username: str) -> User:
    return db.query(User).filter(User.username == username).one()


def _token(user: User) -> str:
    return create_access_token(user.id, user.token_version or 0)


def _local_schemas() -> dict:
    return {
        item["function"]["name"]: item["function"]["parameters"]
        for item in TOOL_DEFINITIONS
    }


def test_mcp_exposes_only_read_only_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert names == set(READ_ONLY_TOOLS)
    assert "create_boarding_draft" not in names
    assert "confirm_boarding_draft" not in names
    assert all(tool.annotations.readOnlyHint for tool in tools)


def test_mcp_schemas_match_local_tool_definitions():
    local = _local_schemas()
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    assert set(tools) == set(READ_ONLY_TOOLS)
    for name, tool in tools.items():
        schema = tool.inputSchema or {}
        assert set(schema.get("properties") or {}) == set(local[name]["properties"])
        assert set(schema.get("required") or []) == set(
            local[name].get("required") or []
        )


def test_mcp_list_pets_uses_token_identity(db, owner_credentials):
    user = _user(db, owner_credentials["username"])
    db.add(Pet(owner_id=user.id, name="MCP豆豆", species="dog"))
    db.commit()

    result = execute_read_tool("list_my_pets", {}, user.id)

    assert result["ok"] is True
    assert [pet["name"] for pet in result["data"]["pets"]] == ["MCP豆豆"]


def test_mcp_cannot_read_another_users_pets(db):
    first = User(
        username=unique_username("mcp_first"),
        password_hash=hash_password("Passw0rd!"),
        nickname="第一个主人",
        role="pet_owner",
        status=1,
    )
    second = User(
        username=unique_username("mcp_second"),
        password_hash=hash_password("Passw0rd!"),
        nickname="第二个主人",
        role="pet_owner",
        status=1,
    )
    db.add_all([first, second])
    db.commit()
    db.add(Pet(owner_id=first.id, name="只属于第一个主人", species="cat"))
    db.commit()

    result = execute_read_tool("list_my_pets", {}, second.id)

    assert result["ok"] is True
    assert all(
        pet["name"] != "只属于第一个主人" for pet in result["data"]["pets"]
    )


def test_mcp_rejects_draft_creation(db, owner_credentials):
    user = _user(db, owner_credentials["username"])

    result = execute_read_tool(
        "create_boarding_draft",
        {
            "pet_name": "MCP豆豆",
            "kennel_code": "K-S-01",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
        },
        user.id,
    )

    assert result == {
        "ok": False,
        "error": "工具未开放：create_boarding_draft",
        "code": 403,
    }


async def _whoami(request):
    return JSONResponse({"user_id": request.scope["state"]["pawcare_user_id"]})


def _auth_client() -> TestClient:
    app = MCPAuthMiddleware(
        Starlette(routes=[Route("/mcp", _whoami, methods=["POST"])])
    )
    return TestClient(app)


def test_mcp_http_auth_requires_bearer(db, owner_credentials):
    user = _user(db, owner_credentials["username"])
    client = _auth_client()

    missing = client.post("/mcp")
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"

    ok = client.post(
        "/mcp", headers={"Authorization": f"Bearer {_token(user)}"}
    )
    assert ok.status_code == 200
    assert ok.json()["user_id"] == user.id


def test_mcp_http_auth_rejects_invalid_token():
    response = _auth_client().post(
        "/mcp", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


def test_mcp_http_auth_rejects_disabled_user(db):
    user = User(
        username=unique_username("mcp_disabled"),
        password_hash=hash_password("Passw0rd!"),
        nickname="已禁用",
        role="pet_owner",
        status=0,
    )
    db.add(user)
    db.commit()

    response = _auth_client().post(
        "/mcp", headers={"Authorization": f"Bearer {_token(user)}"}
    )
    assert response.status_code == 401


def test_mcp_stdio_roundtrip(db, owner_credentials):
    user = _user(db, owner_credentials["username"])
    db.add(Pet(owner_id=user.id, name="MCP stdio 豆豆", species="dog"))
    db.commit()

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server", "--transport", "stdio"],
        cwd=str(BACKEND_DIR),
        env={
            **os.environ,
            "PAWCARE_MCP_TOKEN": _token(user),
            "PYTHONPATH": str(BACKEND_DIR),
            "PYTHONIOENCODING": "utf-8",
        },
    )

    async def roundtrip() -> None:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                listed = await session.list_tools()
                assert {tool.name for tool in listed.tools} == set(
                    READ_ONLY_TOOLS
                )

                called = await session.call_tool("list_my_pets", {})
                payload = json.loads(called.content[0].text)
                assert payload["ok"] is True
                assert any(
                    pet["name"] == "MCP stdio 豆豆"
                    for pet in payload["data"]["pets"]
                )

    asyncio.run(asyncio.wait_for(roundtrip(), timeout=30))
