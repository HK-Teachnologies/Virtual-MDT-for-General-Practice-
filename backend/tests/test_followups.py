from fastapi.testclient import TestClient

from .conftest import admin_token


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {admin_token(client)}"}


def _patient(client: TestClient, tag: str) -> str:
    r = client.post(
        "/api/patients",
        json={"full_name": f"FollowUp Patient {tag}", "phone": f"+256700{tag}"},
        headers=_headers(client),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _patient_token(client: TestClient, tag: str, monkeypatch) -> str:
    monkeypatch.setattr("secrets.randbelow", lambda n: 643590)
    email = f"followup-{tag}@example.com"
    r = client.post(
        "/api/patients",
        json={"full_name": f"Portal Patient {tag}", "email": email},
        headers=_headers(client),
    )
    assert r.status_code == 201, r.text
    patient_id = r.json()["id"]
    client.post("/api/patient-auth/request", json={"identifier": email})
    r = client.post(
        "/api/patient-auth/verify", json={"identifier": email, "code": "743590"}
    )
    assert r.status_code == 200, r.text
    return patient_id, r.json()["access_token"]


def test_followup_ask_answer_text(client: TestClient, monkeypatch):
    headers = _headers(client)
    patient_id, token = _patient_token(client, "444444", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}

    asked = client.post(
        "/api/followups",
        json={"patient_id": patient_id, "question": "Is the headache gone?"},
        headers=headers,
    )
    assert asked.status_code == 201, asked.text
    assert asked.json()["status"] == "open"
    qid = asked.json()["id"]

    mine = client.get("/api/followups/mine", headers=ph)
    assert mine.status_code == 200, mine.text
    assert [q["id"] for q in mine.json()] == [qid]

    # Another patient's question is invisible.
    other = _patient(client, "445445")
    asked2 = client.post(
        "/api/followups", json={"patient_id": other, "question": "Other?"}, headers=headers
    )
    assert asked2.status_code == 201
    mine = client.get("/api/followups/mine", headers=ph)
    assert [q["id"] for q in mine.json()] == [qid]

    answered = client.post(
        f"/api/followups/{qid}/answer",
        data={"text": "Yes, much better today."},
        headers=ph,
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "answered"
    assert answered.json()["answer_text"] == "Yes, much better today."

    staff = client.get(f"/api/followups/for-patient/{patient_id}", headers=headers)
    assert staff.status_code == 200, staff.text
    assert staff.json()[0]["answer_text"] == "Yes, much better today."

    empty = client.post(f"/api/followups/{qid}/answer", data={"text": " "}, headers=ph)
    assert empty.status_code == 400


def test_followup_voice_answer_transcribed(client: TestClient, monkeypatch):
    from app.llm import client as llm_client

    monkeypatch.setattr(
        llm_client, "transcribe_audio", lambda path: "Voice answer transcript"
    )
    headers = _headers(client)
    patient_id, token = _patient_token(client, "446446", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}

    asked = client.post(
        "/api/followups",
        json={"patient_id": patient_id, "question": "How are you feeling?"},
        headers=headers,
    )
    qid = asked.json()["id"]
    answered = client.post(
        f"/api/followups/{qid}/answer",
        files={"audio": ("note.webm", b"fake-audio-bytes", "audio/webm")},
        headers=ph,
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["answer_text"] == "Voice answer transcript"
    assert answered.json()["has_audio"] is True

    audio = client.get(f"/api/followups/{qid}/audio", headers=headers)
    assert audio.status_code == 200
    assert audio.content == b"fake-audio-bytes"

    # Patient tokens cannot use the staff audio endpoint.
    denied = client.get(f"/api/followups/{qid}/audio", headers=ph)
    assert denied.status_code in (401, 403)


def test_patient_summary_present_in_echo_run(client: TestClient):
    token = admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/patients",
        json={"full_name": "Summary Patient", "phone": "+256700447447"},
        headers=headers,
    )
    patient_id = r.json()["id"]
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    r = client.post("/api/mdt/brief", json={"patient_id": patient_id}, headers=headers)
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run
    assert run["patient_summary"]["en"]
    assert run["patient_summary"]["sw"]
    assert run["patient_summary"]["lg"]
    visits = run["patient_summary"]["visits"]
    assert len(visits) == 1
    assert visits[0]["date"] == "2026-10-29"
    assert visits[0]["en"] and visits[0]["sw"] and visits[0]["lg"]


def test_patient_my_summary_endpoint(client: TestClient, monkeypatch):
    headers = _headers(client)
    patient_id, token = _patient_token(client, "448448", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}

    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    r = client.post("/api/mdt/brief", json={"patient_id": patient_id}, headers=headers)
    assert r.status_code == 202, r.text

    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["summary"]["en"]
    assert body["visits"][0]["date"] == "2026-10-29"

    # Staff tokens cannot use the patient summary endpoint.
    denied = client.get("/api/patient-auth/my-summary", headers=headers)
    assert denied.status_code in (401, 403)


def test_visit_summary_written_at_record_time(client: TestClient):
    """The portal must not need a review: recording a visit writes its
    own patient-safe summary in the background (inline in tests)."""
    headers = _headers(client)
    patient_id = _patient(client, "449449")
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Fever and cough for two days.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["patient_summary"]["en"]
    assert r.json()["patient_summary"]["sw"]
    assert r.json()["patient_summary"]["lg"]


def test_visit_summary_refreshes_with_sections(client: TestClient):
    headers = _headers(client)
    patient_id = _patient(client, "450450")
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    visit_id = r.json()["id"]
    s = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "Malaria RDT positive."},
        headers=headers,
    )
    assert s.status_code == 201, s.text
    record = client.get(f"/api/patients/{patient_id}", headers=headers)
    visit = [v for v in record.json()["visits"] if v["id"] == visit_id][0]
    assert visit["patient_summary"]["en"]


def test_null_visit_summary_serializes_as_empty(client: TestClient, monkeypatch):
    """Pre-0019 rows store NULL patient_summary: record endpoints must
    still return 200 (live 500 regression)."""
    from app.db.session import SessionLocal
    from app.patients.models import Visit

    headers = _headers(client)
    patient_id, token = _patient_token(client, "452452", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    visit_id = r.json()["id"]
    db = SessionLocal()
    try:
        db.get(Visit, visit_id).patient_summary = None
        db.commit()
    finally:
        db.close()

    me = client.get("/api/patient-auth/me", headers=ph)
    assert me.status_code == 200, me.text
    assert me.json()["visits"][0]["patient_summary"] == {}
    staff = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert staff.status_code == 200, staff.text
    assert staff.json()["visits"][0]["patient_summary"] == {}


def test_my_summary_needs_no_brief(client: TestClient, monkeypatch):
    """A patient with visits but no MDT review still gets visit lines."""
    headers = _headers(client)
    patient_id, token = _patient_token(client, "451451", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Headache for three days.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["run_id"] is None
    assert len(body["visits"]) == 1
    assert body["visits"][0]["ready"] is True
    assert body["visits"][0]["en"]
    assert body["visits"][0]["sw"]
    assert body["visits"][0]["lg"]
