from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings

# 开发 / 部署统一使用 MySQL；SQLite 仅用于自动化测试。
# check_same_thread=False：TestClient 会在不同线程里使用连接。
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # MySQL 默认 8 小时回收空闲连接，提前回收避免 "MySQL server has gone away"。
    pool_recycle=3600,
    hide_parameters=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键ID", sort_order=-1
    )
    create_time: Mapped[datetime] = mapped_column(
        default=datetime.now, comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
