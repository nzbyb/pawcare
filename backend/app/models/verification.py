from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VerificationCode(Base):
    """邮箱 / 手机验证码。

    只存 HMAC 摘要，不存明文；一条记录只能成功核销一次。
    """

    __tablename__ = "verification_codes"
    __table_args__ = (
        Index(
            "ix_verification_lookup",
            "channel",
            "target",
            "scene",
            "create_time",
        ),
        Index("ix_verification_expires_at", "expires_at"),
        {"comment": "验证码"},
    )

    channel: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="email / phone"
    )
    target: Mapped[str] = mapped_column(
        String(120), nullable=False, comment="邮箱或手机号（已规范化）"
    )
    scene: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="register / reset"
    )
    code_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="验证码 HMAC-SHA256"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="校验失败次数",
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="核销时间"
    )
    request_ip: Mapped[str | None] = mapped_column(String(64), comment="请求 IP")
