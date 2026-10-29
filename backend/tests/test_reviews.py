from fastapi.testclient import TestClient

from .conftest import admin_token


def _staff(client: TestClient, admin: str, email: str, role: str = "doctor"):
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "staff12345", "full_name": email, "role": role},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _patient(client: TestClient, token: str, tag: str) -> dict:
    r = client.post(
        "/api/patients",
        json={"full_name": f"Review Patient {tag}", "phone": f"+256722{tag}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _specialty(client: TestClient, admin: str, name: str) -> dict:
    r = client.post(
        "/api/specialties",
        json={"name": name},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_specialty_crud_and_membership(client: TestClient):
    admin = admin_token(client)
    pharmacist = _staff(client, admin, "spec-pharm@example.com", role="pharmacist")

    spec = _specialty(client, admin, "Pharmacy Test")
    assert spec["member_count"] == 0

    r = client.post(
        f"/api/specialties/{spec['id']}/members",
        json={"user_id": pharmacist},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["member_count"] == 1
    assert r.json()["members"][0]["email"] == "spec-pharm@example.com"

    # The table count and the manage-view list must agree: same join, same rows.
    r = client.get(
        "/api/specialties",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    listed = [s for s in r.json() if s["id"] == spec["id"]][0]
    r = client.get(
        f"/api/specialties/{spec['id']}",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["member_count"] == listed["member_count"] == 1
    assert [m["email"] for m in r.json()["members"]] == ["spec-pharm@example.com"]

    r = client.get(
        "/api/specialties/mine",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200

    r = client.post(
        "/api/specialties",
        json={"name": "Pharmacy Test"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 400, r.text


def test_review_send_respond_close(client: TestClient):
    admin = admin_token(client)
    requester_id, requester_token = _staff_and_token(client, admin, "requester@example.com")
    specialist_id, specialist_token = _staff_and_token(client, admin, "specialist@example.com", role="pharmacist")
    outsider_id, outsider_token = _staff_and_token(client, admin, "outsider@example.com")

    spec = _specialty(client, admin, "HIV care Test")
    r = client.post(
        f"/api/specialties/{spec['id']}/members",
        json={"user_id": specialist_id},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    patient = _patient(client, requester_token, "000011")

    # Send: specialty members become recipients by default.
    r = client.post(
        "/api/reviews",
        json={
            "patient_id": patient["id"],
            "specialty_ids": [spec["id"]],
            "message": "Please advise on this case.",
            "brief": {
                "specialties": ["HIV"],
                "items": [
                    {
                        "specialty": "HIV",
                        "concern": "Check adherence.",
                        "citation": "Visit notes",
                        "certainty": "moderate",
                        "status": "approved",
                    }
                ],
            },
        },
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 201, r.text
    review = r.json()
    assert review["status"] == "pending"
    assert [x["user_id"] for x in review["recipients"]] == [specialist_id]
    assert review["recipients"][0]["specialty_name"] == "HIV care Test"

    # Outsider cannot see it; specialist sees it in the inbox.
    r = client.get(
        f"/api/reviews/{review['id']}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert r.status_code == 403, r.text
    r = client.get(
        "/api/reviews/inbox", headers={"Authorization": f"Bearer {specialist_token}"}
    )
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()] == [review["id"]]
    r = client.get(
        "/api/reviews/requested", headers={"Authorization": f"Bearer {requester_token}"}
    )
    assert [x["response_count"] for x in r.json()] == [0]

    # Specialist responds in text: review flips to responded.
    r = client.post(
        f"/api/reviews/{review['id']}/responses",
        data={"text": "Adherence looks fine; continue ART."},
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_audio"] is False
    r = client.get(
        f"/api/reviews/{review['id']}",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.json()["status"] == "responded"
    assert r.json()["responses"][0]["text"].startswith("Adherence looks fine")

    # Closed reviews reject new responses; only requester/admin closes.
    r = client.patch(
        f"/api/reviews/{review['id']}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 403, r.text
    r = client.patch(
        f"/api/reviews/{review['id']}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"
    r = client.post(
        f"/api/reviews/{review['id']}/responses",
        data={"text": "Too late."},
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 400, r.text


def _staff_and_token(client: TestClient, admin: str, email: str, role: str = "doctor"):
    _staff(client, admin, email, role)
    r = client.post("/api/auth/login", data={"username": email, "password": "staff12345"})
    assert r.status_code == 200, r.text
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()
    return me["id"], r.json()["access_token"]


def _open_review(
    client: TestClient,
    other_id: str,
    requester_token: str,
    patient_id: str,
    spec_id: str,
) -> dict:
    r = client.post(
        "/api/reviews",
        json={
            "patient_id": patient_id,
            "specialty_ids": [spec_id],
            "user_ids": [other_id],
            "message": "Please advise.",
            "brief": {"specialties": [], "items": []},
        },
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_response_image_attach_and_view(client: TestClient):
    admin = admin_token(client)
    requester_id, requester_token = _staff_and_token(client, admin, "img-requester@example.com")
    specialist_id, specialist_token = _staff_and_token(
        client, admin, "img-specialist@example.com", role="pharmacist"
    )
    spec = _specialty(client, admin, "Imaging Test Spec")
    r = client.post(
        f"/api/specialties/{spec['id']}/members",
        json={"user_id": specialist_id},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    patient = _patient(client, requester_token, "000021")
    review = _open_review(client, specialist_id, requester_token, patient["id"], spec["id"])

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = client.post(
        f"/api/reviews/{review['id']}/responses",
        data={"text": "Rash looks like this."},
        files=[("image", ("rash.png", png, "image/png"))],
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_image"] is True
    response_id = r.json()["id"]

    r = client.get(
        f"/api/reviews/responses/{response_id}/image",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.content == png

    r = client.post(
        f"/api/reviews/{review['id']}/responses",
        data={"text": "Not an image."},
        files=[("image", ("note.txt", b"hello", "text/plain"))],
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 400, r.text


def test_response_voice_transcribed_to_english_text_only(
    client: TestClient, monkeypatch
):
    """Voice responses come back as English text; the audio itself is
    never kept or served."""
    from app.llm import client as llm_client

    monkeypatch.setattr(
        llm_client, "transcribe_to_english", lambda path: "The fever is gone"
    )
    admin = admin_token(client)
    requester_id, requester_token = _staff_and_token(client, admin, "vx-requester@example.com")
    specialist_id, specialist_token = _staff_and_token(
        client, admin, "vx-specialist@example.com", role="pharmacist"
    )
    spec = _specialty(client, admin, "Voice Test Spec")
    r = client.post(
        f"/api/specialties/{spec['id']}/members",
        json={"user_id": specialist_id},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    patient = _patient(client, requester_token, "000023")
    review = _open_review(client, specialist_id, requester_token, patient["id"], spec["id"])

    r = client.post(
        f"/api/reviews/{review['id']}/responses",
        files=[("audio", ("note.webm", b"fake-audio-bytes", "audio/webm"))],
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "The fever is gone"
    assert r.json()["has_audio"] is False
    response_id = r.json()["id"]

    missing = client.get(
        f"/api/reviews/responses/{response_id}/audio",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert missing.status_code == 404


def test_open_reviews_for_patient(client: TestClient):
    admin = admin_token(client)
    requester_id, requester_token = _staff_and_token(client, admin, "fp-requester@example.com")
    other_id, _ = _staff_and_token(client, admin, "fp-other@example.com")
    spec = _specialty(client, admin, "Gate Test Spec")
    patient = _patient(client, requester_token, "000022")

    r = client.get(
        f"/api/reviews/for-patient/{patient['id']}",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == []

    review = _open_review(client, other_id, requester_token, patient["id"], spec["id"])
    r = client.get(
        f"/api/reviews/for-patient/{patient['id']}",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()] == [review["id"]]
    assert r.json()[0]["status"] == "pending"

    r = client.patch(
        f"/api/reviews/{review['id']}",
        json={"status": "closed"},
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    r = client.get(
        f"/api/reviews/for-patient/{patient['id']}",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == []

    r = client.get(
        "/api/reviews/for-patient/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    assert r.status_code == 404, r.text
