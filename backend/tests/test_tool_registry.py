"""统一工具注册表：外部 MCP 只读边界、降级与结果防护。"""

import asyncio
import json
import sys
from pathlib import Path

from app.agent.mcp_client import (
    MCPServerConfig,
    parse_server_configs,
    public_tool_name,
)
from app.agent.registry import ToolRegistry

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND_DIR / "evaluation" / "fixtures" / "fake_mcp_server.py"


def _config(mode: str, name: str | None = None) -> MCPServerConfig:
    return MCPServerConfig(
        name=name or f"fake_{mode}",
        transport="stdio",
        command=sys.executable,
        args=(str(FIXTURE), "--mode", mode),
        env={"PYTHONIOENCODING": "utf-8"},
    )


def _load(*configs: MCPServerConfig, **kwargs) -> ToolRegistry:
    registry = ToolRegistry(
        configs=list(configs),
        discovery_timeout=kwargs.pop("discovery_timeout", 15.0),
        call_timeout=kwargs.pop("call_timeout", 8.0),
        cache_seconds=0,
    )
    asyncio.run(registry.ensure_loaded())
    return registry


def _definitions(registry: ToolRegistry) -> dict[str, dict]:
    return {
        item["function"]["name"]: item["function"]
        for item in registry.definitions()
    }


def test_registry_keeps_only_read_only_tools():
    registry = _load(_config("write"))
    definitions = _definitions(registry)

    assert set(definitions) == {"mcp__fake_write__safe_read"}
    assert all("delete_all_pets" not in name for name in definitions)
    assert definitions["mcp__fake_write__safe_read"]["description"].startswith(
        "[外部 MCP:fake_write]"
    )


def test_registry_filters_injected_tool_description():
    registry = _load(_config("malicious"))
    definitions = _definitions(registry)

    description = definitions["mcp__fake_malicious__echo"]["description"]
    assert "已过滤" in description
    assert "API key" not in description
    assert "忽略之前" not in description

    result = asyncio.run(
        registry.execute("mcp__fake_malicious__echo", {"text": "你好"})
    )
    assert result == {"ok": True, "data": {"echo": "你好"}}


def test_registry_degrades_when_server_is_unreachable():
    broken = MCPServerConfig(
        name="broken",
        transport="stdio",
        command=str(BACKEND_DIR / "no-such-python.exe"),
    )
    registry = _load(broken, discovery_timeout=3.0)

    assert registry.definitions() == []
    assert registry.diagnostics()[0]["status"] == "error"


def test_registry_keeps_working_servers_when_one_fails():
    broken = MCPServerConfig(
        name="broken",
        transport="stdio",
        command=str(BACKEND_DIR / "no-such-python.exe"),
    )
    registry = _load(broken, _config("malicious"), discovery_timeout=3.0)

    names = set(_definitions(registry))
    assert names == {
        "mcp__fake_malicious__echo",
        "mcp__fake_malicious__benign",
    }
    statuses = {item["name"]: item["status"] for item in registry.diagnostics()}
    assert statuses == {"broken": "error", "fake_malicious": "ok"}


def test_registry_times_out_slow_tool():
    registry = _load(_config("slow"), call_timeout=1.0)

    result = asyncio.run(
        registry.execute("mcp__fake_slow__slow_tool", {})
    )

    assert result["ok"] is False
    assert result["code"] == 504


def test_registry_rejects_oversized_result():
    registry = _load(_config("huge"))

    result = asyncio.run(registry.execute("mcp__fake_huge__huge_tool", {}))

    assert result == {
        "ok": False,
        "error": "外部工具返回结果过大",
        "code": 413,
    }


def test_registry_namespaces_tool_name_collision():
    registry = _load(_config("collision"))

    names = set(_definitions(registry))
    assert "mcp__fake_collision__list_my_pets" in names
    assert "list_my_pets" not in names


def test_public_tool_name_fits_openai_limit():
    name = public_tool_name("s" * 40, "t" * 40)
    assert len(name) <= 64
    assert name.startswith("mcp__")


def test_parse_server_configs_expands_secrets(monkeypatch):
    monkeypatch.setenv("FAKE_MCP_TOKEN", "secret-token")
    configs = parse_server_configs(
        json.dumps(
            [
                {
                    "name": "remote",
                    "transport": "streamable-http",
                    "url": "https://example.com/mcp",
                    "headers": {"Authorization": "Bearer ${FAKE_MCP_TOKEN}"},
                }
            ]
        )
    )

    assert len(configs) == 1
    assert configs[0].transport == "streamable-http"
    assert configs[0].headers["Authorization"] == "Bearer secret-token"


def test_parse_server_configs_ignores_invalid_input():
    assert parse_server_configs("") == []
    assert parse_server_configs("{not-json") == []
    assert parse_server_configs(json.dumps({"name": "x"})) == []


def test_agent_runtime_calls_external_tool(client, owner_headers, monkeypatch):
    """站内 Agent 的模型能看到外部工具，并按命名空间路由执行。"""
    from app.agent import runtime
    from app.agent.runtime import LLMResponse, ToolCall
    from app.services import agent_service

    registry = _load(_config("malicious"))

    async def fake_loader():
        return registry

    class ExternalToolLLM:
        def __init__(self) -> None:
            self.tool_sets: list[list[dict]] = []

        async def complete(self, messages, tools):
            self.tool_sets.append(tools)
            if len(self.tool_sets) == 1:
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call-ext-1",
                            name="mcp__fake_malicious__echo",
                            arguments={"text": "你好"},
                        )
                    ]
                )
            return LLMResponse(content="外部工具已调用")

    llm = ExternalToolLLM()
    monkeypatch.setattr(runtime, "load_tool_registry", fake_loader)
    monkeypatch.setattr(agent_service, "get_llm", lambda: llm)

    body = client.post(
        "/api/agent/chat",
        headers=owner_headers,
        json={"messages": [{"role": "user", "content": "调用外部工具"}]},
    ).json()

    assert body["code"] == 200, body
    definitions = {
        item["function"]["name"]: item["function"]
        for item in llm.tool_sets[0]
    }
    assert "mcp__fake_malicious__echo" in definitions
    assert "list_my_pets" in definitions
    assert "API key" not in definitions["mcp__fake_malicious__echo"]["description"]

    event = body["data"]["tool_events"][0]
    assert event["name"] == "mcp__fake_malicious__echo"
    assert event["status"] == "ok"
