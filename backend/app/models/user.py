from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户"}

    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False, comment="登录账号"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希"
    )
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, comment="昵称")
    role: Mapped[str] = mapped_column(
        String(30),
        default="pet_owner",
        nullable=False,
        index=True,
        comment="角色: pet_owner / boarding_staff / admin",
    )
    phone: Mapped[str | None] = mapped_column(String(30), comment="手机号")
    status: Mapped[int] = mapped_column(
        default=1, nullable=False, comment="1-正常, 0-禁用"
    )
    token_version: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
        comment="令牌版本号，改密码时+1",
    )
