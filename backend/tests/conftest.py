import os
import tempfile
import uuid
from pathlib import Path

# 必须在导入 app 之前设置：app.config 在导入时就会读取环境变量。
TEST_DB = Path(tempfile.gettempdir()) / "pawcare_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_" + "x" * 40
os.environ["REDIS_URL"] = ""
os.environ["LLM_API_KEY"] = "test-key"
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "pawcare_test_uploads")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.limiter import limiter
from app.main import app
from app.models.user import User
from app.utils.password import hash_password

# 测试里不需要限流，避免多个用例共用登录接口时被 429。
limiter.enabled = False


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def unique_username(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def login(client, username: str, password: str = "Passw0rd!") -> str:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    return body["data"]["token"]


def register_and_login(client, username: str, password: str = "Passw0rd!") -> str:
    register_resp = client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert register_resp.json()["code"] == 200, register_resp.text
    return login(client, username, password)


@pytest.fixture()
def owner_credentials(client):
    username = unique_username("owner")
    token = register_and_login(client, username)
    return {"username": username, "password": "Passw0rd!", "token": token}


@pytest.fixture()
def owner_headers(owner_credentials):
    return {"Authorization": f"Bearer {owner_credentials['token']}"}


@pytest.fixture()
def staff_headers(client, db):
    username = unique_username("staff")
    db.add(
        User(
            username=username,
            password_hash=hash_password("Passw0rd!"),
            nickname="寄养员",
            role="boarding_staff",
            status=1,
        )
    )
    db.commit()
    token = login(client, username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_owner_headers(client):
    username = unique_username("other")
    token = register_and_login(client, username)
    return {"Authorization": f"Bearer {token}"}
