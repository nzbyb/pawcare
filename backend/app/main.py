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
from app.config import ALLOWED_ORIGINS, UPLOAD_PATH
from app.database import Base, engine
from app.limiter import limiter

# 必须导入所有模型，Base.metadata 才是完整的。
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine.dialect.name == "postgresql":
        # 生产库表结构由 Alembic 管理（Docker entrypoint 会先执行 upgrade head）。
        # 这里只确保扩展存在，兼容手工迁移后的首次启动。
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    else:
        # 本地 SQLite 用 create_all 快速起飞；生产环境不再隐式建表。
        Base.metadata.create_all(bind=engine)
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
