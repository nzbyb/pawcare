"""邮箱 / 手机验证码的签发与核销。"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.verification import VerificationCode
from app.services import mailer, sms

logger = logging.getLogger(__name__)

Channel = Literal["email", "phone"]
Scene = Literal["register", "reset"]

CHANNELS = ("email", "phone")
SCENES = ("register", "reset")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_target(channel: str, target: str) -> str:
    """规范化并校验联系方式。"""
    value = (target or "").strip()
    if channel == "email":
        value = value.lower()
        if len(value) > 120 or not _EMAIL_RE.match(value):
            raise BusinessException(message="邮箱格式不正确")
        return value
    if channel == "phone":
        value = re.sub(r"[\s-]", "", value)
        if not _PHONE_RE.match(value):
            raise BusinessException(message="请输入 11 位大陆手机号")
        return value
    raise BusinessException(message="不支持的验证方式")


def _hash_code(channel: str, target: str, scene: str, code: str) -> str:
    """用服务端密钥做 HMAC，数据库泄漏也拿不到明文验证码。"""
    key = f"pawcare-verification:{settings.JWT_SECRET_KEY}".encode()
    payload = f"{channel}:{target}:{scene}:{code}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _dispatch(channel: str, target: str, code: str) -> None:
    if channel == "email":
        if mailer.is_configured():
            mailer.send_verification_code(target, code)
            return
        if settings.VERIFY_CODE_DEBUG:
            logger.warning("[验证码-本地调试] 邮箱 %s 的验证码是 %s", target, code)
            return
        raise BusinessException(
            message="邮件服务未配置，请联系管理员", code=503
        )
    sms.send_verification_code(target, code)


def issue_code(
    db: Session,
    channel: str,
    target: str,
    scene: str,
    request_ip: str | None = None,
) -> dict[str, int | str | None]:
    """签发验证码；返回冷却时间，调试模式下附带验证码。"""
    if channel not in CHANNELS:
        raise BusinessException(message="不支持的验证方式")
    if scene not in SCENES:
        raise BusinessException(message="不支持的业务场景")
    target = normalize_target(channel, target)
    now = datetime.now()

    last = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.channel == channel,
            VerificationCode.target == target,
            VerificationCode.scene == scene,
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if last:
        elapsed = (now - last.create_time).total_seconds()
        if elapsed < settings.VERIFY_CODE_RESEND_SECONDS:
            wait = int(settings.VERIFY_CODE_RESEND_SECONDS - elapsed) + 1
            raise BusinessException(
                message=f"请 {wait} 秒后再获取验证码", code=429
            )

    hour_ago = now - timedelta(hours=1)
    recent = (
        db.query(func.count(VerificationCode.id))
        .filter(
            VerificationCode.channel == channel,
            VerificationCode.target == target,
            VerificationCode.scene == scene,
            VerificationCode.create_time >= hour_ago,
        )
        .scalar()
        or 0
    )
    if recent >= settings.VERIFY_CODE_HOURLY_LIMIT:
        raise BusinessException(
            message="获取验证码过于频繁，请稍后再试", code=429
        )

    # 新码生效后，之前未使用的码立即作废，避免一码多用。
    db.query(VerificationCode).filter(
        VerificationCode.channel == channel,
        VerificationCode.target == target,
        VerificationCode.scene == scene,
        VerificationCode.consumed_at.is_(None),
    ).update({VerificationCode.consumed_at: now})

    code = f"{secrets.randbelow(1_000_000):06d}"
    record = VerificationCode(
        channel=channel,
        target=target,
        scene=scene,
        code_hash=_hash_code(channel, target, scene, code),
        expires_at=now + timedelta(seconds=settings.VERIFY_CODE_TTL_SECONDS),
        request_ip=request_ip,
    )
    db.add(record)
    db.flush()

    try:
        _dispatch(channel, target, code)
    except Exception:
        db.rollback()
        raise
    db.commit()

    payload: dict[str, int | str | None] = {
        "cooldown": settings.VERIFY_CODE_RESEND_SECONDS,
        "expires_in": settings.VERIFY_CODE_TTL_SECONDS,
    }
    if settings.VERIFY_CODE_DEBUG:
        payload["debug_code"] = code
    return payload


def verify_code(
    db: Session, channel: str, target: str, scene: str, code: str
) -> None:
    """校验并核销验证码；失败时抛出业务异常。"""
    target = normalize_target(channel, target)
    now = datetime.now()

    record = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.channel == channel,
            VerificationCode.target == target,
            VerificationCode.scene == scene,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if not record:
        raise BusinessException(message="请先获取验证码")
    if record.expires_at <= now:
        raise BusinessException(message="验证码已过期，请重新获取")
    if record.attempts >= settings.VERIFY_CODE_MAX_ATTEMPTS:
        raise BusinessException(
            message="验证码错误次数过多，请重新获取", code=429
        )

    expected = _hash_code(channel, target, scene, code)
    if not hmac.compare_digest(expected, record.code_hash):
        record.attempts = (record.attempts or 0) + 1
        db.commit()
        raise BusinessException(message="验证码不正确")

    record.consumed_at = now
    db.commit()
