def create_pet(client, headers, name="豆豆"):
    return client.post(
        "/api/pets",
        headers=headers,
        json={
            "name": name,
            "species": "dog",
            "breed": "柯基",
            "gender": "male",
            "neutered": True,
            "allergies": "鸡肉",
            "notes": "怕生",
        },
    )


def test_create_list_get_update_delete_pet(client, owner_headers):
    resp = create_pet(client, owner_headers)
    body = resp.json()
    assert body["code"] == 200
    pet = body["data"]
    assert pet["name"] == "豆豆"
    assert pet["owner_id"] > 0

    resp = client.get("/api/pets", headers=owner_headers)
    pets = resp.json()["data"]
    assert len(pets) == 1

    resp = client.get(f"/api/pets/{pet['id']}", headers=owner_headers)
    assert resp.json()["data"]["breed"] == "柯基"

    resp = client.put(
        f"/api/pets/{pet['id']}",
        headers=owner_headers,
        json={"notes": "已不怕生"},
    )
    assert resp.json()["data"]["notes"] == "已不怕生"

    resp = client.delete(f"/api/pets/{pet['id']}", headers=owner_headers)
    assert resp.json()["code"] == 200

    resp = client.get(f"/api/pets/{pet['id']}", headers=owner_headers)
    assert resp.json()["code"] == 400


def test_owner_cannot_access_others_pet(client, owner_headers, other_owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]

    resp = client.get(f"/api/pets/{pet['id']}", headers=other_owner_headers)
    assert resp.json()["code"] == 403

    resp = client.put(
        f"/api/pets/{pet['id']}",
        headers=other_owner_headers,
        json={"name": "偷改"},
    )
    assert resp.json()["code"] == 403


def test_staff_cannot_create_or_modify_pet(client, owner_headers, staff_headers):
    resp = create_pet(client, staff_headers)
    assert resp.json()["code"] == 403

    pet = create_pet(client, owner_headers).json()["data"]
    resp = client.put(
        f"/api/pets/{pet['id']}",
        headers=staff_headers,
        json={"notes": "寄养员修改"},
    )
    assert resp.json()["code"] == 403

    # 寄养员可以只读查看，用于安排寄养
    resp = client.get(f"/api/pets/{pet['id']}", headers=staff_headers)
    assert resp.json()["code"] == 200


def test_weight_records(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]

    resp = client.post(
        f"/api/pets/{pet['id']}/weights",
        headers=owner_headers,
        json={"record_date": "2026-10-01", "weight_kg": 12.5},
    )
    assert resp.json()["code"] == 200

    resp = client.post(
        f"/api/pets/{pet['id']}/weights",
        headers=owner_headers,
        json={"record_date": "2026-10-15", "weight_kg": 12.8},
    )
    assert resp.json()["code"] == 200

    resp = client.get(f"/api/pets/{pet['id']}/weights", headers=owner_headers)
    records = resp.json()["data"]
    assert [item["weight_kg"] for item in records] == [12.5, 12.8]


def test_invalid_weight_rejected(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    resp = client.post(
        f"/api/pets/{pet['id']}/weights",
        headers=owner_headers,
        json={"record_date": "2026-10-01", "weight_kg": 0},
    )
    assert resp.status_code == 422
