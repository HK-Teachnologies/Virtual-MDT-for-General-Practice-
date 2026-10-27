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
