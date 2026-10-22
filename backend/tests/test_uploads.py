import base64

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_upload_pet_image(client, owner_headers):
    resp = client.post(
        "/api/uploads",
        headers=owner_headers,
        data={"purpose": "pet"},
        files={"file": ("avatar.png", PNG_1PX, "image/png")},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    url = body["data"]["url"]
    assert url.startswith("/uploads/pet/")
    assert url.endswith(".png")

    served = client.get(url)
    assert served.status_code == 200
    assert served.content == PNG_1PX


def test_upload_detects_type_from_content(client, owner_headers):
    resp = client.post(
        "/api/uploads",
        headers=owner_headers,
        data={"purpose": "report"},
        files={"file": ("not-really.jpg", PNG_1PX, "image/jpeg")},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["url"].endswith(".png")


def test_upload_rejects_non_image(client, owner_headers):
    resp = client.post(
        "/api/uploads",
        headers=owner_headers,
        files={"file": ("fake.png", b"hello, not an image", "image/png")},
    )
    assert resp.json()["code"] == 400


def test_upload_requires_login(client):
    resp = client.post(
        "/api/uploads",
        files={"file": ("avatar.png", PNG_1PX, "image/png")},
    )
    assert resp.status_code == 401
