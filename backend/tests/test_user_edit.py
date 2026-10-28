from fastapi.testclient import TestClient

from .conftest import admin_token


def _staff(client: TestClient, admin: str, email: str, role: str = "doctor") -> str:
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "staff12345", "full_name": email, "role": role},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]
    r = client.post("/api/auth/login", data={"username": email, "password": "staff12345"})
    assert r.status_code == 200, r.text
    return user_id, r.json()["access_token"]


def test_admin_edits_user(client: TestClient):
    admin = admin_token(client)
    user_id, _ = _staff(client, admin, "edit-me@example.com", role="nurse")

    r = client.patch(
        f"/api/auth/users/{user_id}",
        json={"full_name": "Edited Name", "role": "pharmacist"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Edited Name"
    assert r.json()["role"] == "pharmacist"

    r = client.patch(
        f"/api/auth/users/{user_id}",
        json={"email": "edited@example.com", "password": "newpassword1"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/auth/login", data={"username": "edited@example.com", "password": "newpassword1"}
    )
    assert r.status_code == 200, r.text


def test_admin_cannot_demote_self(client: TestClient):
    admin = admin_token(client, email="selfdemote@example.com")
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {admin}"}
    ).json()
    r = client.patch(
        f"/api/auth/users/{me['id']}",
        json={"role": "doctor"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 400, r.text


def test_non_admin_cannot_edit_users(client: TestClient):
    admin = admin_token(client)
    _, staff_token = _staff(client, admin, "noedit@example.com")
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {staff_token}"}
    ).json()
    r = client.patch(
        f"/api/auth/users/{me['id']}",
        json={"full_name": "Hacker"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 403, r.text
