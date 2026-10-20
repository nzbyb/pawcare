"""验证码邮件发送。

QQ / 163 邮箱用 SMTP 授权码（不是登录密码）：
     QQ：smtp.qq.com:465（SSL）
    163：smtp.163.com:465（SSL）
"""

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.common.exceptions import BusinessException
from app.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_verification_code(to: str, code: str) -> None:
    minutes = max(1, settings.VERIFY_CODE_TTL_SECONDS // 60)
    message = EmailMessage()
    message["Subject"] = "【PawCare】邮箱验证码"
    message["From"] = formataddr(
        ("PawCare", settings.SMTP_FROM or settings.SMTP_USER)
    )
    message["To"] = to
    message.set_content(
        f"你的验证码是 {code}，{minutes} 分钟内有效。\n\n"
        "如果这不是你本人的操作，请忽略这封邮件。\n"
        "PawCare 不会通过任何方式向你索要验证码。\n"
    )

    try:
        if settings.SMTP_USE_SSL:
            client = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
        else:
            client = smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
            client.starttls()

        with client:
            client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # 不记录授权码 / 密码，只记录异常类型与信息。
        logger.warning("验证码邮件发送失败：%s: %s", type(exc).__name__, exc)
        raise BusinessException(
            message="验证码邮件发送失败，请稍后重试", code=503
        ) from exc
