import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from app.api import api
from app.common.exceptions import (
    BusinessException,
    business_exception_handler,
    global_exception_handler,
    http_exception_handler,
    rate_limit_exception_handler,
    validation_exception_handler,
)
from app.config import ALLOWED_ORIGINS, UPLOAD_PATH, settings
from app.database import Base, engine
from app.limiter import limiter

logger = logging.getLogger(__name__)

# 必须导入所有模型，Base.metadata 才是完整的。
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine.dialect.name == "sqlite":
        # 自动化测试 / 临时 SQLite 用 create_all 快速起飞。
        Base.metadata.create_all(bind=engine)
    # MySQL 的表结构统一由 Alembic 管理：
    # 本地 `python -m alembic upgrade head`，容器由 entrypoint 自动执行。
    if settings.VERIFY_CODE_DEBUG:
        logger.warning(
            "VERIFY_CODE_DEBUG 已开启：验证码会随接口响应返回，仅限本地调试，部署时必须关闭。"
        )
    yield


app = FastAPI(title="PawCare API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.state.limiter = limiter

app.mount("/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")


@app.get("/")
def root():
    return {"message": "PawCare API is running"}
