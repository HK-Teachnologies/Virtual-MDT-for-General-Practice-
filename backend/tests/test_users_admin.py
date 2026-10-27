from fastapi.testclient import TestClient

from .conftest import admin_token


def _login(client: TestClient, email: str) -> str:
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "secret123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_list_users_admin_only(client: TestClient):
    admin = {"Authorization": f"Bearer {admin_token(client)}"}

    for email, role in [("doctor9@example.com", "doctor"), ("boss9@example.com", "admin")]:
        r = client.post(
            "/api/auth/register",
            json={"email": email, "password": "secret123", "role": role},
            headers=admin,
        )
        assert r.status_code == 201, r.text

    listed = client.get("/api/auth/users", headers=admin)
    assert listed.status_code == 200, listed.text
    emails = [u["email"] for u in listed.json()]
    assert "doctor9@example.com" in emails
    assert "boss9@example.com" in emails

    doctor = {"Authorization": f"Bearer {_login(client, 'doctor9@example.com')}"}
    forbidden = client.get("/api/auth/users", headers=doctor)
    assert forbidden.status_code == 403

    anon = client.get("/api/auth/users")
    assert anon.status_code == 401
