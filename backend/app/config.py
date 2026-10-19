from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置。

    真实值放在 backend/.env；模板见 backend/.env.example。
    环境变量优先级高于 .env，测试用 conftest 直接覆盖 DATABASE_URL。
    """

    DATABASE_URL: str = (
        "postgresql+psycopg://pawcare:pawcare_dev_password@127.0.0.1:5432/pawcare"
    )

    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"

    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-flash"
    LLM_BASE_URL: str = "https://api.deepseek.com"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 留空 = 进程内存限流；Docker 部署时注入 redis://redis:6379/0
    REDIS_URL: str = ""

    AI_MAX_CONCURRENCY: int = 3
    AGENT_MAX_TOOL_CALLS: int = 6
    AGENT_TIMEOUT_SECONDS: int = 30
    LLM_MAX_TOKENS: int = 1024

    # RAG：本地开发用 fastembed + SQLite；生产环境同一套接口可切到 pgvector。
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
