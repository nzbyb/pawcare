import uuid
from datetime import datetime, timedelta

from app.models.user import User
from app.models.verification import VerificationCode
from tests.conftest import (
    login,
    register_and_login,
    register_payload,
    request_code,
    unique_username,
)


def unique_phone() -> str:
    return "139" + f"{uuid.uuid4().int % 10**8:08d}"


def test_send_code_cooldown(client):
    email = f"{unique_username('cd')}@example.com"
    first = client.post(
        "/api/auth/verification-code",
        json={"channel": "email", "target": email, "scene": "register"},
    ).json()
    assert first["code"] == 200
    assert first["data"]["cooldown"] == 60

    second = client.post(
        "/api/auth/verification-code",
        json={"channel": "email", "target": email, "scene": "register"},
    ).json()
    assert second["code"] == 429
    assert "秒后再获取" in second["message"]


def test_invalid_target_rejected(client):
    email_resp = client.post(
        "/api/auth/verification-code",
        json={"channel": "email", "target": "not-an-email", "scene": "register"},
    ).json()
    assert email_resp["code"] == 400
    assert "邮箱" in email_resp["message"]

    phone_resp = client.post(
        "/api/auth/verification-code",
        json={"channel": "phone", "target": "12345", "scene": "register"},
    ).json()
    assert phone_resp["code"] == 400
    assert "手机号" in phone_resp["message"]


def test_register_requires_correct_code(client):
    username = unique_username("nocode")
    payload = register_payload(client, username)
    payload["code"] = "000000"
    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 400
    assert "验证码" in body["message"]


def test_register_with_email_code(client):
    username = unique_username("email")
    email = f"{username}@example.com"
    payload = register_payload(client, username, target=email)
    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 200, body
    assert body["data"]["email"] == email
    assert login(client, username)


def test_duplicate_email_rejected(client):
    username = unique_username("dupemail")
    email = f"{username}@example.com"
    register_and_login(client, username)

    payload = register_payload(
        client, unique_username("dupemail2"), target=f"{username}2@example.com"
    )
    payload["email"] = email
    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 400
    assert "已被注册" in body["message"]


def test_register_with_phone_code(client, db):
    username = unique_username("phone")
    phone = unique_phone()
    payload = register_payload(client, username, channel="phone", target=phone)
    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 200, body
    assert body["data"]["phone"] == phone

    user = db.query(User).filter(User.username == username).one()
    assert user.phone_verified_at is not None
    assert user.email is None


def test_expired_code_rejected(client, db):
    username = unique_username("expired")
    email = f"{username}@example.com"
    payload = register_payload(client, username, target=email)

    record = (
        db.query(VerificationCode)
        .filter(VerificationCode.target == email)
        .order_by(VerificationCode.id.desc())
        .one()
    )
    record.expires_at = datetime.now() - timedelta(minutes=1)
    db.commit()

    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 400
    assert "过期" in body["message"]


def test_wrong_code_attempts_limited(client):
    username = unique_username("attempts")
    email = f"{username}@example.com"
    correct = request_code(client, "email", email)

    for index in range(5):
        payload = {
            "username": f"{username}_{index}",
            "password": "Passw0rd!",
            "email": email,
            "code": "000000",
        }
        body = client.post("/api/auth/register", json=payload).json()
        assert body["code"] == 400
        assert "验证码不正确" in body["message"]

    payload = {
        "username": username,
        "password": "Passw0rd!",
        "email": email,
        "code": correct,
    }
    body = client.post("/api/auth/register", json=payload).json()
    assert body["code"] == 429
    assert "错误次数过多" in body["message"]


def test_reset_password_with_email_code(client):
    username = unique_username("reset")
    email = f"{username}@example.com"
    register_and_login(client, username)

    code = request_code(client, "email", email, scene="reset")
    body = client.post(
        "/api/auth/password/reset",
        json={
            "channel": "email",
            "target": email,
            "code": code,
            "new_password": "NewPassw0rd!",
        },
    ).json()
    assert body["code"] == 200, body
    assert body["data"]["username"] == username

    old_login = client.post(
        "/api/auth/login", json={"username": username, "password": "Passw0rd!"}
    ).json()
    assert old_login["code"] == 400

    new_login = client.post(
        "/api/auth/login", json={"username": username, "password": "NewPassw0rd!"}
    ).json()
    assert new_login["code"] == 200


def test_login_locked_after_repeated_failures(client):
    username = unique_username("lock")
    register_and_login(client, username)

    last_body = None
    for _ in range(5):
        last_body = client.post(
            "/api/auth/login", json={"username": username, "password": "WrongPass1!"}
        ).json()
    assert last_body is not None
    assert last_body["code"] == 429
    assert "锁定" in last_body["message"]

    # 锁定期间即使密码正确也不能登录
    body = client.post(
        "/api/auth/login", json={"username": username, "password": "Passw0rd!"}
    ).json()
    assert body["code"] == 429
    assert "锁定" in body["message"]
