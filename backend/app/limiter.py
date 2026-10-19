from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import BASE_DIR, settings

# 留空时用进程内存；Docker 部署时注入 Redis URL。
# 注意：Redis 不可用时 slowapi 不会自动降级，生产上要么保证 Redis 可用，要么留空。
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL or "memory://",
    # SlowAPI 0.1.x 会自动读取 cwd 下的 .env，且用系统默认编码（Windows 为 GBK）。
    # 本项目 .env 是 UTF-8，含中文注释时会直接 UnicodeDecodeError。
    # 指向一个不存在的专用文件，让 SlowAPI 跳过这次读取；应用配置仍由 pydantic-settings 负责。
    config_filename=str(BASE_DIR / ".slowapi.env"),
)
