from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = {"comment": "系统设置（键值）"}

    key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False, comment="设置项键名"
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="设置项取值"
    )
    description: Mapped[str | None] = mapped_column(String(200), comment="说明")
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class LoginLog(Base):
    __tablename__ = "login_logs"
    __table_args__ = (
        Index("ix_login_logs_username_time", "username", "create_time"),
        {"comment": "登录日志"},
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    username: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="登录时填写的账号"
    )
    success: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="success",
        comment="success / wrong_password / no_user / locked / disabled",
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
