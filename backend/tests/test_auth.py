from fastapi.testclient import TestClient

from .conftest import admin_token


def test_register_login_me(client: TestClient):
    admin = {"Authorization": f"Bearer {admin_token(client)}"}

    r = client.post(
        "/api/auth/register",
        json={
            "email": "doc@example.com",
            "password": "secret123",
            "full_name": "Doc",
            "role": "doctor",
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "doc@example.com"
    assert r.json()["role"] == "doctor"
    assert "hashed_password" not in r.json()

    dup = client.post(
        "/api/auth/register",
        json={"email": "doc@example.com", "password": "secret123"},
        headers=admin,
    )
    assert dup.status_code == 400

    bad_role = client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "secret123", "role": "surgeon"},
        headers=admin,
    )
    assert bad_role.status_code == 422

    login = client.post(
        "/api/auth/login", data={"username": "doc@example.com", "password": "secret123"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    bad = client.post(
        "/api/auth/login", data={"username": "doc@example.com", "password": "wrong"}
    )
    assert bad.status_code == 401

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "doc@example.com"

    anon = client.get("/api/auth/me")
    assert anon.status_code == 401


def test_register_requires_admin(client: TestClient):
    payload = {"email": "nurse@example.com", "password": "secret123", "role": "nurse"}

    anon = client.post("/api/auth/register", json=payload)
    assert anon.status_code == 401

    admin = {"Authorization": f"Bearer {admin_token(client)}"}
    created = client.post("/api/auth/register", json=payload, headers=admin)
    assert created.status_code == 201, created.text

    doctor_login = client.post(
        "/api/auth/login",
        data={"username": "nurse@example.com", "password": "secret123"},
    )
    doctor = {"Authorization": f"Bearer {doctor_login.json()['access_token']}"}
    refused = client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "secret123"},
        headers=doctor,
    )
    assert refused.status_code == 403


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
