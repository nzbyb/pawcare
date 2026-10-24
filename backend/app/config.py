from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置。

    真实值放在 backend/.env；模板见 backend/.env.example。
    环境变量优先级高于 .env，测试用 conftest 直接覆盖 DATABASE_URL。
    """

    DATABASE_URL: str = (
        "mysql+pymysql://pawcare:pawcare_dev_password@127.0.0.1:3306/pawcare?charset=utf8mb4"
    )

    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"

    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-flash"
    LLM_BASE_URL: str = "https://api.deepseek.com"

    # ---------- 邮箱 / 短信验证码 ----------
    # QQ 邮箱：smtp.qq.com / 465 / SSL；SMTP_PASSWORD 填授权码，不是登录密码。
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_TIMEOUT_SECONDS: int = 10
    # 短信：console 只写后端日志，不会真发；接入阿里云时在 services/sms.py 扩展。
    SMS_PROVIDER: str = "console"
    VERIFY_CODE_TTL_SECONDS: int = 300
    VERIFY_CODE_RESEND_SECONDS: int = 60
    VERIFY_CODE_HOURLY_LIMIT: int = 5
    VERIFY_CODE_MAX_ATTEMPTS: int = 5
    # 仅本地调试：未配置 SMTP 时把验证码写日志并随响应返回。部署必须为 false。
    VERIFY_CODE_DEBUG: bool = False
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # ---------- 支付 ----------
    # mock：本地模拟收银台，不产生真实资金（默认，测试环境）；
    # alipay：支付宝沙箱 / 正式环境的电脑网站支付。
    PAYMENT_PROVIDER: str = "mock"
    PAYMENT_TTL_MINUTES: int = 15
    # 前端地址：模拟收银台二维码和支付宝同步跳转都会回到这里。
    PAYMENT_MOCK_BASE_URL: str = "http://localhost:5173"
    # 后端公网地址，用于生成支付宝异步通知地址；本地联调需填内网穿透地址。
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # 支付宝开放平台（沙箱与正式环境的网关不同，密钥也各自独立）
    ALIPAY_APP_ID: str = ""
    # 可以是 PEM 内容，也可以是文件路径；推荐用路径，避免多行配置。
    ALIPAY_PRIVATE_KEY: str = ""
    ALIPAY_PUBLIC_KEY: str = ""
    ALIPAY_GATEWAY: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    # 收银台异步通知 / 同步跳转；留空时按 PUBLIC_BASE_URL 和 PAYMENT_MOCK_BASE_URL 生成。
    ALIPAY_NOTIFY_URL: str = ""
    ALIPAY_SELLER_ID: str = ""
    ALIPAY_QUERY_TIMEOUT_SECONDS: float = 5.0

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 留空 = 进程内存限流；Docker 部署时注入 redis://redis:6379/0
    REDIS_URL: str = ""

    # 进程内定时任务：每天扫描一次健康提醒并补站内通知。
    # 测试关闭；多进程部署时每个进程都会跑，靠 dedupe_key 保证不重复。
    SCHEDULER_ENABLED: bool = True

    AI_MAX_CONCURRENCY: int = 3
    # 主实现是显式循环；langgraph 仅用于对照实验，需额外安装依赖。
    AGENT_ENGINE: str = "explicit"
    AGENT_MAX_TOOL_CALLS: int = 6
    AGENT_TIMEOUT_SECONDS: int = 30
    LLM_MAX_TOKENS: int = 1024

    # ---------- MCP Server（对外提供能力） ----------
    # 单次工具调用超时；stdio 的 token 只从环境变量读取。
    MCP_TOOL_TIMEOUT_SECONDS: int = 5
    # 每个用户每分钟的 MCP HTTP 请求数；0 表示关闭。
    MCP_RATE_LIMIT_PER_MINUTE: int = 60
    # 是否把 MCP 调用写入 mcp_audit_logs。
    MCP_AUDIT_ENABLED: bool = True

    # ---------- MCP Client（接入外部 Server） ----------
    # JSON 数组，示例见 .env.example；留空时站内 Agent 只使用本地工具。
    MCP_CLIENT_SERVERS: str = ""
    MCP_CLIENT_DISCOVERY_TIMEOUT_SECONDS: float = 3.0
    MCP_CLIENT_CALL_TIMEOUT_SECONDS: float = 8.0
    # 工具发现结果缓存时间，避免每轮对话都拉起 stdio 子进程。
    MCP_CLIENT_CACHE_SECONDS: int = 300

    # RAG：向量以 JSON 文本存库，检索在应用层计算余弦相似度；MySQL / SQLite 通用。
    RAG_ENABLED: bool = True
    RAG_EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    RAG_CACHE_DIR: str = ".fastembed_cache"
    RAG_TOP_K: int = 3
    RAG_MIN_SCORE: float = 0.45

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

_WEAK_JWT_SECRETS = {
    "please_generate_a_random_secret_at_least_32_chars",
    "your_secret_key",
    "secret",
    "changeme",
}


def _validate_jwt_secret() -> None:
    secret = settings.JWT_SECRET_KEY.strip()
    if len(secret) < 32 or secret in _WEAK_JWT_SECRETS:
        raise RuntimeError(
            "JWT_SECRET_KEY 不合法：长度至少 32 位，且不能使用 .env.example 里的示例值。\n"
            '生成方法：python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )


_validate_jwt_secret()

UPLOAD_PATH = Path(settings.UPLOAD_DIR)
if not UPLOAD_PATH.is_absolute():
    UPLOAD_PATH = BASE_DIR / UPLOAD_PATH
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

ALLOWED_ORIGINS = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
}
