from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.users.models import User


def _register(client: TestClient, email: str):
    r = client.post(
        "/api/auth/register", json={"email": email, "password": "secret123"}
    )
    assert r.status_code == 201, r.text


def _promote(email: str):
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = "admin"
        db.commit()
    finally:
        db.close()


def _login(client: TestClient, email: str) -> str:
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "secret123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_list_users_admin_only(client: TestClient):
    _register(client, "doctor9@example.com")
    _register(client, "boss9@example.com")
    _promote("boss9@example.com")

    admin = {"Authorization": f"Bearer {_login(client, 'boss9@example.com')}"}
    doctor = {"Authorization": f"Bearer {_login(client, 'doctor9@example.com')}"}

    listed = client.get("/api/auth/users", headers=admin)
    assert listed.status_code == 200, listed.text
    emails = [u["email"] for u in listed.json()]
    assert "doctor9@example.com" in emails
    assert "boss9@example.com" in emails

    forbidden = client.get("/api/auth/users", headers=doctor)
    assert forbidden.status_code == 403

    anon = client.get("/api/auth/users")
    assert anon.status_code == 401
