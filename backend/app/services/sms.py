"""短信发送。

当前只有 console 一种实现：不真正发短信，把验证码写到后端日志，
用于没有短信账号时的本地演示。接入阿里云 / 腾讯云时在这里加分支，
调用方（verification_service）不需要改。
"""

import logging

from app.common.exceptions import BusinessException
from app.config import settings

logger = logging.getLogger(__name__)


def send_verification_code(phone: str, code: str) -> None:
    if settings.SMS_PROVIDER == "console":
        logger.warning("[短信-本地演示] 手机 %s 的验证码是 %s", phone, code)
        return
    raise BusinessException(message=f"短信服务未配置（provider={settings.SMS_PROVIDER}）", code=503)
