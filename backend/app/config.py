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
    # 当前只有 mock 渠道：二维码指向本地模拟收银台，不产生真实资金。
    PAYMENT_TTL_MINUTES: int = 15
    # 二维码里写的前端地址；换域名时同步修改，否则扫码打不开。
    PAYMENT_MOCK_BASE_URL: str = "http://localhost:5173"

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
