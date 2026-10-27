from fastapi.testclient import TestClient


def test_register_login_me(client: TestClient):
    r = client.post(
        "/api/auth/register",
        json={"email": "doc@example.com", "password": "secret123", "full_name": "Doc"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "doc@example.com"
    assert "hashed_password" not in r.json()

    dup = client.post(
        "/api/auth/register", json={"email": "doc@example.com", "password": "secret123"}
    )
    assert dup.status_code == 400

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


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
