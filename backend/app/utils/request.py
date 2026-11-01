from fastapi import Request


def client_ip(request: Request) -> str | None:
    """真实客户端 IP：优先取反向代理写入的 X-Forwarded-For 首段。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:255] if ua else None
