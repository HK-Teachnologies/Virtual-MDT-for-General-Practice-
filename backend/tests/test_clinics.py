from fastapi.testclient import TestClient

from .conftest import admin_token


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {admin_token(client)}"}


def _login(client: TestClient, email: str) -> dict:
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "secret123"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_clinics_admin_and_visit_link(client: TestClient):
    headers = _headers(client)

    created = client.post(
        "/api/clinics", json={"name": "Test Clinic"}, headers=headers
    )
    assert created.status_code == 201, created.text
    clinic_id = created.json()["id"]

    dup = client.post("/api/clinics", json={"name": "Test Clinic"}, headers=headers)
    assert dup.status_code == 400

    listed = client.get("/api/clinics", headers=headers)
    assert listed.status_code == 200
    assert any(c["id"] == clinic_id for c in listed.json())

    client.post(
        "/api/auth/register",
        json={"email": "staff@example.com", "password": "secret123", "role": "nurse"},
        headers=headers,
    )
    staff = _login(client, "staff@example.com")
    forbidden = client.post(
        "/api/clinics", json={"name": "Nope"}, headers=staff
    )
    assert forbidden.status_code == 403

    patient = client.post(
        "/api/patients",
        json={"full_name": "Clinic Patient", "phone": "+256700000009"},
        headers=headers,
    )
    patient_id = patient.json()["id"]

    visit = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Review", "clinic_id": clinic_id},
        headers=headers,
    )
    assert visit.status_code == 201, visit.text
    assert visit.json()["clinic"]["name"] == "Test Clinic"

    bad_clinic = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Review", "clinic_id": "nope"},
        headers=headers,
    )
    assert bad_clinic.status_code == 400

    read = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert read.json()["visits"][0]["clinic"]["name"] == "Test Clinic"
