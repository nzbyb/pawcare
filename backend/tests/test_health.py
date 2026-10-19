from tests.test_pets import create_pet


def test_health_record_creates_reminder(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]

    resp = client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "狂犬疫苗",
            "record_date": "2026-10-01",
            "next_due_date": "2027-10-01",
            "note": "年度加强针",
        },
    )
    body = resp.json()
    assert body["code"] == 200
    record = body["data"]

    resp = client.get(f"/api/pets/{pet['id']}/reminders", headers=owner_headers)
    reminders = resp.json()["data"]
    assert len(reminders) == 1
    assert reminders[0]["due_date"] == "2027-10-01"
    assert reminders[0]["source_health_record_id"] == record["id"]
    assert reminders[0]["status"] == "pending"


def test_update_health_record_replaces_reminder(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    record = client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "deworm",
            "title": "体内驱虫",
            "record_date": "2026-10-01",
            "next_due_date": "2026-11-01",
        },
    ).json()["data"]

    resp = client.put(
        f"/api/health-records/{record['id']}",
        headers=owner_headers,
        json={"next_due_date": "2026-12-01"},
    )
    assert resp.json()["code"] == 200

    reminders = client.get(
        f"/api/pets/{pet['id']}/reminders", headers=owner_headers
    ).json()["data"]
    assert len(reminders) == 1
    assert reminders[0]["due_date"] == "2026-12-01"


def test_delete_health_record_dismisses_reminder(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    record = client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "visit",
            "title": "复查",
            "record_date": "2026-10-01",
            "next_due_date": "2026-10-20",
        },
    ).json()["data"]

    resp = client.delete(f"/api/health-records/{record['id']}", headers=owner_headers)
    assert resp.json()["code"] == 200

    records = client.get(
        f"/api/pets/{pet['id']}/health-records", headers=owner_headers
    ).json()["data"]
    assert records == []

    reminders = client.get(
        f"/api/pets/{pet['id']}/reminders", headers=owner_headers
    ).json()["data"]
    assert reminders == []


def test_other_owner_cannot_read_health_records(
    client, owner_headers, other_owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    resp = client.get(
        f"/api/pets/{pet['id']}/health-records", headers=other_owner_headers
    )
    assert resp.json()["code"] == 403
