"""MCP 传输层认证。

身份只从令牌来，工具参数里没有 user_id：
- stdio：启动时从 PAWCARE_MCP_TOKEN 解析一次，适合本地单用户接入。
- Streamable HTTP：每个请求校验 Authorization: Bearer <JWT>，支持多用户。

令牌校验与 REST 接口保持一致：签名、过期时间、用户状态、token_version。
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

import anyio
from mcp.server.fastmcp import Context
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.database import SessionLocal
from app.models.user import User
from app.utils.jwt import decode_access_token

logger = logging.getLogger(__name__)

# HTTP 请求内传递当前用户；stdio 模式没有请求，使用 _stdio_user_id。
_current_user_id: ContextVar[int | None] = ContextVar(
    "pawcare_mcp_user_id", default=None
)
_stdio_user_id: int | None = None


class MCPAuthError(Exception):
    """令牌缺失、过期、用户被禁用或版本不匹配。"""


def resolve_user_id(token: str) -> int:
    """校验 JWT 并返回用户 ID；失败时抛 MCPAuthError。"""
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise MCPAuthError("登录已失效，请重新登录") from exc

    user_id = payload.get("user_id")
    if not user_id:
        raise MCPAuthError("无效的登录凭证")

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise MCPAuthError("用户不存在")
        if user.status != 1:
            raise MCPAuthError("用户被禁用")
        if payload.get("ver", 0) != (user.token_version or 0):
            raise MCPAuthError("密码已变更，请重新登录")
        return user.id


def set_stdio_user(token: str) -> int:
    """stdio 启动时固定用户；进程内只服务这一个身份。"""
    global _stdio_user_id
    _stdio_user_id = resolve_user_id(token)
    return _stdio_user_id


def current_user_id(ctx: Context | None = None) -> int:
    """按 HTTP 请求 → 上下文变量 → stdio 的顺序取当前用户。"""
    if ctx is not None:
        request_context = getattr(ctx, "request_context", None)
        request = getattr(request_context, "request", None)
        if request is not None:
            state = getattr(request, "scope", {}).get("state") or {}
            user_id = state.get("pawcare_user_id")
            if user_id:
                return int(user_id)

    user_id = _current_user_id.get()
    if user_id:
        return user_id
    if _stdio_user_id:
        return _stdio_user_id
    raise MCPAuthError("未认证：请在 Authorization 头中携带 Bearer token")


class MCPAuthMiddleware:
    """给 Streamable HTTP 入口加 Bearer 校验。

    纯 ASGI 实现，避免 BaseHTTPMiddleware 对长连接/流式响应的干扰。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # 预检请求不携带 Authorization，交给内层返回。
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            await self._reject(scope, receive, send, "缺少 Bearer token")
            return

        try:
            user_id = await anyio.to_thread.run_sync(
                resolve_user_id, token.strip()
            )
        except MCPAuthError as exc:
            await self._reject(scope, receive, send, str(exc))
            return

        scope.setdefault("state", {})["pawcare_user_id"] = user_id
        context_token = _current_user_id.set(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_user_id.reset(context_token)

    async def _reject(
        self, scope: Scope, receive: Receive, send: Send, message: str
    ) -> None:
        response = JSONResponse(
            {"error": message},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)
