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


def _create_reminder(client, headers, due_date: str = "2026-11-01") -> tuple[dict, dict]:
    pet = create_pet(client, headers).json()["data"]
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=headers,
        json={
            "record_type": "deworm",
            "title": "体内驱虫",
            "record_date": "2026-10-01",
            "next_due_date": due_date,
        },
    )
    reminders = client.get(
        f"/api/pets/{pet['id']}/reminders", headers=headers
    ).json()["data"]
    assert len(reminders) == 1
    return pet, reminders[0]


def test_complete_reminder(client, owner_headers, db):
    from app.models.audit import AuditLog

    pet, reminder = _create_reminder(client, owner_headers)

    resp = client.patch(
        f"/api/pets/{pet['id']}/reminders/{reminder['id']}",
        headers=owner_headers,
        json={"status": "done"},
    )
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["status"] == "done"

    assert (
        client.get(
            f"/api/pets/{pet['id']}/reminders", headers=owner_headers
        ).json()["data"]
        == []
    )

    db.expire_all()
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "reminder.done", AuditLog.target_id == reminder["id"])
        .first()
    )
    assert audit is not None
    assert audit.after_data["status"] == "done"


def test_snooze_reminder(client, owner_headers, db):
    from app.models.reminder import Reminder

    pet, reminder = _create_reminder(client, owner_headers)

    resp = client.patch(
        f"/api/pets/{pet['id']}/reminders/{reminder['id']}",
        headers=owner_headers,
        json={"snooze_days": 7},
    )
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["due_date"] == "2026-11-08"
    assert body["data"]["status"] == "pending"

    db.expire_all()
    stored = db.get(Reminder, reminder["id"])
    assert stored is not None
    assert stored.due_date.isoformat() == "2026-11-08"
    assert stored.notified_at is None
    assert stored.dedupe_key.endswith("2026-11-08")


def test_reminder_update_requires_exactly_one_action(client, owner_headers):
    pet, reminder = _create_reminder(client, owner_headers)
    url = f"/api/pets/{pet['id']}/reminders/{reminder['id']}"

    assert client.patch(url, headers=owner_headers, json={}).json()["code"] == 400
    both = client.patch(
        url, headers=owner_headers, json={"status": "done", "snooze_days": 7}
    ).json()
    assert both["code"] == 400


def test_reminder_update_permissions(
    client, owner_headers, other_owner_headers, staff_headers
):
    pet, reminder = _create_reminder(client, owner_headers)
    url = f"/api/pets/{pet['id']}/reminders/{reminder['id']}"

    other = client.patch(
        url, headers=other_owner_headers, json={"status": "done"}
    ).json()
    assert other["code"] == 403

    staff = client.patch(url, headers=staff_headers, json={"status": "done"}).json()
    assert staff["code"] == 403


def test_completed_reminder_cannot_be_updated_again(client, owner_headers):
    pet, reminder = _create_reminder(client, owner_headers)
    url = f"/api/pets/{pet['id']}/reminders/{reminder['id']}"

    assert (
        client.patch(url, headers=owner_headers, json={"status": "done"}).json()["code"]
        == 200
    )
    again = client.patch(url, headers=owner_headers, json={"snooze_days": 7}).json()
    assert again["code"] == 400
