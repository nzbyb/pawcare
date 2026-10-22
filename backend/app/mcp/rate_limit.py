"""MCP HTTP 入口的按用户限流。

复用 slowapi 已依赖的 limits 存储：本地是进程内存，部署时注入
``REDIS_URL`` 就是 Redis 计数。限流按用户在认证之后进行，避免把
多用户共享的出口 IP 当成同一个人。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from limits.storage import MemoryStorage, storage_from_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    retry_after: int


class MCPRateLimiter:
    def __init__(
        self,
        per_minute: int,
        storage_uri: str = "",
        window_seconds: int = 60,
    ) -> None:
        self.limit = max(0, int(per_minute))
        self.window_seconds = max(1, int(window_seconds))
        self._storage = None
        if not self.limit:
            return
        try:
            self._storage = storage_from_string(storage_uri or "memory://")
        except Exception:
            # Redis 配错时退化为单进程限流，至少不会把入口打挂。
            logger.exception("MCP 限流存储初始化失败，退回进程内存")
            self._storage = MemoryStorage()

    @property
    def enabled(self) -> bool:
        return self.limit > 0 and self._storage is not None

    def check(self, key: str) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision(True, self.limit, 0)
        try:
            hits = self._storage.incr(
                f"pawcare:mcp:rate:{key}", self.window_seconds
            )
        except Exception:
            # 限流基础设施故障时放行，业务可用性优先；异常会留在日志里。
            logger.exception("MCP 限流计数失败，本次放行")
            return RateLimitDecision(True, self.limit, 0)
        if hits is None:
            return RateLimitDecision(True, self.limit, 0)
        return RateLimitDecision(
            allowed=hits <= self.limit,
            limit=self.limit,
            retry_after=self.window_seconds,
        )


def build_rate_limiter(storage_uri: str | None = None) -> MCPRateLimiter:
    from app.config import settings

    return MCPRateLimiter(
        settings.MCP_RATE_LIMIT_PER_MINUTE,
        settings.REDIS_URL if storage_uri is None else storage_uri,
    )
