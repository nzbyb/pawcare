"""登录日志：只记录，不参与鉴权。

登录成功与失败都会落一条记录，用于管理端查看异常登录；写入失败不能
影响登录本身，因此这里吞掉数据库异常。
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.system import LoginLog


def record(
    db: Session,
    *,
    username: str,
    success: bool,
    reason: str,
    user_id: int | None = None,
    ip: str | None = None,
    agent: str | None = None,
) -> None:
    try:
        db.add(
            LoginLog(
                user_id=user_id,
                username=(username or "")[:50] or "—",
                success=success,
                reason=reason,
                ip=ip,
                user_agent=agent,
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
