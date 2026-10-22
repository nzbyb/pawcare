"""外部 MCP 工具客户端。

站内 Agent 通过这里消费外部 MCP Server 的能力，和 ``app/mcp/server.py``
（PawCare 对外提供能力）是两个方向：

- 只接受带 ``readOnlyHint=True`` 的工具；写工具、破坏性工具一律不注册。
- 工具描述和返回值都按不可信数据处理：描述会过滤疑似指令，返回值限制大小。
- 每次发现 / 调用都新建一次会话，进程或连接不会跨请求复用，避免状态串扰。

配置来自 ``MCP_CLIENT_SERVERS``（JSON 数组），见 ``.env.example``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, Tool

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 600
MAX_PROPERTY_DESCRIPTION_CHARS = 200
MAX_TOOLS_PER_SERVER = 50
MAX_RESULT_CHARS = 32_000

# 外部工具描述里出现这些字样时，不把原文交给模型，避免工具描述变成注入入口。
_INJECTION_PATTERN = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions?"
    r"|忽略\s*(之前|以上|前面|此前).{0,8}(指令|提示)"
    r"|system\s*prompt|系统提示词|开发者消息|developer\s+message"
    r"|api[\s_-]?key|access[\s_-]?token|密钥",
    re.IGNORECASE,
)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]")
_SCHEMA_KEYS = {
    "type",
    "description",
    "enum",
    "properties",
    "required",
    "items",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "default",
}


@dataclass(frozen=True)
class MCPServerConfig:
    """一个外部 MCP Server 的连接配置。"""

    name: str
    transport: str = "stdio"
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPServerConfig":
        if not isinstance(data, dict):
            raise ValueError("MCP Server 配置必须是对象")

        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("MCP Server 配置缺少 name")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            raise ValueError(f"MCP Server 名称不合法：{name}")

        transport = str(data.get("transport") or "stdio").strip().lower()
        if transport in {"http", "streamable_http", "streamable-http"}:
            transport = "streamable-http"
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError(f"不支持的 MCP 传输方式：{transport}")

        raw_args = data.get("args") or []
        if not isinstance(raw_args, list):
            raise ValueError("args 必须是数组")
        raw_env = data.get("env") or {}
        raw_headers = data.get("headers") or {}
        if not isinstance(raw_env, dict) or not isinstance(raw_headers, dict):
            raise ValueError("env / headers 必须是对象")

        config = cls(
            name=name,
            transport=transport,
            command=_expand(data.get("command")),
            args=tuple(_expand(item) for item in raw_args),
            env={str(k): _expand(v) for k, v in raw_env.items()},
            cwd=_expand(data.get("cwd")),
            url=_expand(data.get("url")),
            headers={str(k): _expand(v) for k, v in raw_headers.items()},
        )
        if config.transport == "stdio" and not config.command:
            raise ValueError("stdio 模式需要 command")
        if config.transport == "streamable-http" and not config.url:
            raise ValueError("streamable-http 模式需要 url")
        return config


def _expand(value: Any) -> Any:
    """展开 ``${ENV_VAR}``，让 token 留在环境变量而不是配置文件里。"""
    if value is None:
        return None
    return os.path.expandvars(str(value))


def parse_server_configs(raw: str | None) -> list[MCPServerConfig]:
    """解析环境变量里的 JSON 配置；单个服务写错只跳过它，不影响启动。"""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("MCP_CLIENT_SERVERS 不是合法 JSON，已忽略外部工具")
        return []
    if not isinstance(data, list):
        logger.warning("MCP_CLIENT_SERVERS 必须是 JSON 数组，已忽略外部工具")
        return []

    configs: list[MCPServerConfig] = []
    seen: set[str] = set()
    for item in data:
        try:
            config = MCPServerConfig.from_dict(item)
        except ValueError as exc:
            logger.warning("跳过无效的 MCP Server 配置：%s", exc)
            continue
        if config.name in seen:
            logger.warning("MCP Server 重名，已跳过：%s", config.name)
            continue
        seen.add(config.name)
        configs.append(config)
    return configs


@asynccontextmanager
async def connect(config: MCPServerConfig) -> AsyncIterator[ClientSession]:
    """建立一次 MCP 会话；退出上下文时进程 / 连接一起关闭。"""
    if config.transport == "stdio":
        params = StdioServerParameters(
            command=config.command or "",
            args=list(config.args),
            env={**os.environ, **config.env},
            cwd=config.cwd,
            encoding="utf-8",
            encoding_error_handler="replace",
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return

    async with streamablehttp_client(
        config.url or "", headers=config.headers or None
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools(config: MCPServerConfig, timeout: float) -> list[Tool]:
    """拉取工具列表；超时或连接失败时抛异常，由注册表统一降级。"""
    with anyio.fail_after(timeout):
        async with connect(config) as session:
            result = await session.list_tools()
            return list(result.tools)


async def call_tool(
    config: MCPServerConfig,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: float,
) -> CallToolResult:
    with anyio.fail_after(timeout):
        async with connect(config) as session:
            return await session.call_tool(tool_name, arguments)


def sanitize_text(text: str | None, limit: int) -> str:
    """压缩空白并截断；命中指令式内容时整段替换。"""
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    if _INJECTION_PATTERN.search(clean):
        return "（外部工具描述含疑似指令内容，已过滤）"
    return clean if len(clean) <= limit else clean[:limit] + "…"


def public_tool_name(server: str, tool_name: str) -> str:
    """给外部工具加命名空间，同时满足 OpenAI 函数名 64 字符限制。"""
    raw = _SAFE_NAME.sub("_", f"mcp__{server}__{tool_name}")
    if len(raw) <= 64:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{raw[:55]}_{digest}"


def clean_schema(schema: Any) -> dict[str, Any]:
    """只保留 OpenAI 兼容的 JSON Schema 子集，丢弃 $ref 等外部扩展。"""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    cleaned: dict[str, Any] = {}
    for key in _SCHEMA_KEYS:
        if key not in schema:
            continue
        value = schema[key]
        if key == "description":
            cleaned[key] = sanitize_text(
                str(value), MAX_PROPERTY_DESCRIPTION_CHARS
            )
        elif key == "properties" and isinstance(value, dict):
            properties = {}
            for prop_name, prop_schema in list(value.items())[:40]:
                if not isinstance(prop_name, str):
                    continue
                properties[prop_name] = clean_schema(prop_schema)
            cleaned["properties"] = properties
        elif key == "required" and isinstance(value, list):
            cleaned["required"] = [str(item) for item in value]
        elif key == "items":
            cleaned[key] = clean_schema(value)
        elif key == "enum" and isinstance(value, list):
            cleaned[key] = value[:50]
        else:
            cleaned[key] = value

    if cleaned.get("type") == "object" and "properties" not in cleaned:
        cleaned["properties"] = {}
    if "type" not in cleaned:
        cleaned["type"] = "object"
        cleaned.setdefault("properties", {})

    # required 只能引用保留下来的属性，否则部分模型服务会拒绝整个工具表。
    if "required" in cleaned and "properties" in cleaned:
        cleaned["required"] = [
            name for name in cleaned["required"] if name in cleaned["properties"]
        ]
    return cleaned


def build_tool_definition(
    server: str, tool: Tool, public_name: str
) -> dict[str, Any]:
    description = sanitize_text(tool.description, MAX_DESCRIPTION_CHARS)
    if not description:
        description = "外部 MCP 只读工具"
    return {
        "type": "function",
        "function": {
            "name": public_name,
            "description": f"[外部 MCP:{server}] {description}",
            "parameters": clean_schema(tool.inputSchema),
        },
    }


def normalize_result(result: CallToolResult) -> dict[str, Any]:
    """把 MCP 的 content / structuredContent 统一成站内工具返回格式。"""
    texts = [
        block.text
        for block in result.content
        if getattr(block, "type", None) == "text"
    ]
    text = "\n".join(texts).strip()

    if result.isError:
        return {
            "ok": False,
            "error": text[:500] or "外部工具执行失败",
            "code": 502,
        }

    text_payload: Any = None
    if text:
        try:
            text_payload = json.loads(text)
        except json.JSONDecodeError:
            text_payload = None

    structured = result.structuredContent
    structured_payload = structured if isinstance(structured, dict) else None

    # FastMCP 会把字符串返回值再包一层 structuredContent（{"result": "..."}），
    # 所以优先使用能解析出 ok 字段的文本，避免丢掉站内约定的返回结构。
    if isinstance(text_payload, dict) and "ok" in text_payload:
        normalized = text_payload
    elif (
        isinstance(structured_payload, dict)
        and "ok" in structured_payload
    ):
        normalized = structured_payload
    elif isinstance(text_payload, dict):
        normalized = {"ok": True, "data": text_payload}
    elif structured_payload is not None:
        normalized = {"ok": True, "data": structured_payload}
    else:
        normalized = {
            "ok": True,
            "data": {"text": text or "外部工具没有返回内容"},
        }

    encoded = json.dumps(normalized, ensure_ascii=False, default=str)
    if len(encoded) > MAX_RESULT_CHARS:
        return {"ok": False, "error": "外部工具返回结果过大", "code": 413}
    return normalized
