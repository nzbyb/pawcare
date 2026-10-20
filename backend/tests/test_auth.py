from tests.conftest import (
    register_and_login,
    register_payload,
    unique_username,
)


def test_register_login_and_me(client):
    username = unique_username("auth")
    token = register_and_login(client, username)

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["username"] == username
    assert body["data"]["role"] == "pet_owner"
    assert body["data"]["email"] == f"{username}@example.com"


def test_duplicate_username_rejected(client):
    username = unique_username("dup")
    register_and_login(client, username)

    payload = register_payload(client, username, target=f"{username}2@example.com")
    resp = client.post("/api/auth/register", json=payload)
    body = resp.json()
    assert body["code"] == 400
    assert "已存在" in body["message"]


def test_wrong_password_rejected(client):
    username = unique_username("wrong")
    register_and_login(client, username)

    resp = client.post(
        "/api/auth/login", json={"username": username, "password": "WrongPass1!"}
    )
    body = resp.json()
    assert body["code"] == 400
    assert "密码" in body["message"]


def test_short_password_rejected(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": unique_username("short"), "password": "123"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == 422


def test_change_password_invalidates_old_token(client):
    username = unique_username("pwd")
    old_token = register_and_login(client, username)
    old_headers = {"Authorization": f"Bearer {old_token}"}

    resp = client.put(
        "/api/auth/password",
        headers=old_headers,
        json={"old_password": "Passw0rd!", "new_password": "NewPassw0rd!"},
    )
    body = resp.json()
    assert body["code"] == 200
    new_token = body["data"]["token"]

    old_resp = client.get("/api/auth/me", headers=old_headers)
    assert old_resp.status_code == 401

    new_resp = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert new_resp.json()["code"] == 200


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
