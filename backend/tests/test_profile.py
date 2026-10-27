from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    client.post(
        "/api/auth/register",
        json={"email": "clinician@example.com", "password": "secret123"},
    )
    login = client.post(
        "/api/auth/login",
        data={"username": "clinician@example.com", "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_profile_flow(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "doctor"

    first = client.get("/api/profile/me", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["specialty"] is None
    assert first.json()["user_id"] == me.json()["id"]

    updated = client.patch(
        "/api/profile/me",
        headers=headers,
        json={"specialty": "General practice", "facility": "District Hospital"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["specialty"] == "General practice"

    again = client.get("/api/profile/me", headers=headers)
    assert again.json()["facility"] == "District Hospital"

    anon = client.get("/api/profile/me")
    assert anon.status_code == 401
