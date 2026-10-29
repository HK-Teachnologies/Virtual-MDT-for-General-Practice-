from fastapi.testclient import TestClient

from app.core.config import settings

from .conftest import admin_token


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {admin_token(client)}"}


def test_patient_flow(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    headers = _headers(client)

    created = client.post(
        "/api/patients",
        json={
            "full_name": "Test Patient",
            "phone": "+256700000001",
            "sex": "Female",
            "district": "Wakiso",
            "address": "Kira",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["district"] == "Wakiso"
    assert created.json()["sex"] == "Female"
    patient_id = created.json()["id"]

    dup = client.post(
        "/api/patients",
        json={"full_name": "Copy", "phone": "+256700000001"},
        headers=headers,
    )
    assert dup.status_code == 400

    listed = client.get("/api/patients", headers=headers)
    assert listed.status_code == 200
    assert any(p["id"] == patient_id for p in listed.json())

    visit = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Two-week cough", "source": "typed"},
        files=[("files", ("slip.jpg", b"fake-bytes", "image/jpeg"))],
        headers=headers,
    )
    assert visit.status_code == 201, visit.text
    assert len(visit.json()["attachments"]) == 1
    attachment_id = visit.json()["attachments"][0]["id"]
    visit_id = visit.json()["id"]

    read = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert read.status_code == 200
    assert len(read.json()["visits"]) == 1
    assert read.json()["visits"][0]["notes"] == "Two-week cough"

    past = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Old review", "visit_date": "2026-01-15"},
        headers=headers,
    )
    assert past.status_code == 201, past.text
    assert past.json()["visit_date"] == "2026-01-15"

    bad_date = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Old review", "visit_date": "not-a-date"},
        headers=headers,
    )
    assert bad_date.status_code == 400

    download = client.get(
        f"/api/patients/visits/{visit_id}/attachments/{attachment_id}",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"fake-bytes"

    missing = client.post(
        "/api/patients/nope/visits", data={"notes": "x"}, headers=headers
    )
    assert missing.status_code == 404

    anon = client.get("/api/patients")
    assert anon.status_code == 401


def test_patient_details_and_measurements_editable(client: TestClient):
    headers = _headers(client)
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Measure Patient",
            "phone": "+256700000201",
            "weight_kg": 68.5,
            "height_cm": 172,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["weight_kg"] == 68.5
    assert created.json()["height_cm"] == 172
    patient_id = created.json()["id"]

    # Nonsense measurements are rejected on create and on edit.
    bad = client.post(
        "/api/patients",
        json={"full_name": "Bad Measure", "weight_kg": -5},
        headers=headers,
    )
    assert bad.status_code == 400, bad.text

    patched = client.patch(
        f"/api/patients/{patient_id}",
        json={"weight_kg": 70.0, "district": "Mbarara"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["weight_kg"] == 70.0
    assert patched.json()["height_cm"] == 172
    assert patched.json()["district"] == "Mbarara"

    bad_patch = client.patch(
        f"/api/patients/{patient_id}", json={"height_cm": 0}, headers=headers
    )
    assert bad_patch.status_code == 400, bad_patch.text

    missing = client.patch(
        "/api/patients/00000000-0000-0000-0000-000000000000",
        json={"weight_kg": 70},
        headers=headers,
    )
    assert missing.status_code == 404

    anon = client.patch(f"/api/patients/{patient_id}", json={"weight_kg": 70})
    assert anon.status_code == 401
