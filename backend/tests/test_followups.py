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


def _ready_brief(client: TestClient, headers: dict, patient_id: str) -> dict:
    r = client.post("/api/mdt/brief", json={"patient_id": patient_id}, headers=headers)
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run
    return run


def test_brief_writes_no_patient_summary(client: TestClient):
    """The release gate: a finished brief must not publish anything to
    the patient until the doctor prepares and releases a summary."""
    headers = _headers(client)
    patient_id = _patient(client, "447447")
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    run = _ready_brief(client, headers, patient_id)
    assert run["patient_summary"] == {}
    assert run["summary_status"] == "draft"


def test_prepare_summary_uses_only_signed_off_items(
    client: TestClient, monkeypatch
):
    """Approved + doctor-edited wording reach the prompt; suggested,
    rejected and removed points never do."""
    import json as _json

    from app.core.config import settings
    from app.llm import client as llm_client

    captured = {}

    def recorder(*, system, user, kind, max_tokens=8000, retries=1):
        captured["payload"] = _json.loads(user)
        return {
            "en": "Recorded summary.",
            "sw": "Muhtasari uliorekodiwa.",
            "lg": "Okusumulula okukwata.",
        }

    headers = _headers(client)
    patient_id = _patient(client, "453453")
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    run = _ready_brief(client, headers, patient_id)
    assert len(run["items"]) >= 2
    first, second = run["items"][0]["id"], run["items"][1]["id"]
    ok = client.patch(
        f"/api/mdt/items/{first}", json={"status": "approved"}, headers=headers
    )
    assert ok.status_code == 200, ok.text
    ok = client.patch(
        f"/api/mdt/items/{second}",
        json={"status": "edited", "edited_text": "Doctor wording: continue current care."},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text

    # Record the exact prompt payload the prepare step sends.
    monkeypatch.setattr(settings, "llm_provider", "recorded")
    monkeypatch.setattr(llm_client, "complete_json", recorder)
    prep = client.post(
        f"/api/mdt/runs/{run['id']}/patient-summary", headers=headers
    )
    assert prep.status_code == 202, prep.text
    points = captured["payload"]["approved_points"]
    assert len(points) == 2
    texts = " | ".join(p["point"] for p in points)
    assert "Review ART adherence" in texts
    assert "Doctor wording: continue current care." in texts
    assert "interactions" not in captured["payload"]
    summary = prep.json()["run"]["patient_summary"]
    assert summary["en"] == "Recorded summary."
    assert prep.json()["run"]["summary_status"] == "draft"

    # Rejecting everything leaves nothing to say: no prompt, no summary.
    client.patch(f"/api/mdt/items/{first}", json={"status": "rejected"}, headers=headers)
    client.patch(
        f"/api/mdt/items/{second}", json={"status": "rejected"}, headers=headers
    )
    captured.clear()
    prep = client.post(
        f"/api/mdt/runs/{run['id']}/patient-summary", headers=headers
    )
    assert prep.status_code == 202, prep.text
    assert captured == {}


def test_patient_my_summary_endpoint(client: TestClient, monkeypatch):
    headers = _headers(client)
    patient_id, token = _patient_token(client, "448448", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}

    v = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    visit_id = v.json()["id"]

    # Drafts never appear: the visit exists but nothing is released.
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.status_code == 200, mine.text
    assert mine.json()["visits"][0]["ready"] is False
    assert mine.json()["visits"][0]["en"] == ""

    rel = client.post(
        f"/api/patients/visits/{visit_id}/release", headers=headers
    )
    assert rel.status_code == 200, rel.text
    assert rel.json()["summary_status"] == "released"

    run = _ready_brief(client, headers, patient_id)
    for item in run["items"]:
        client.patch(
            f"/api/mdt/items/{item['id']}",
            json={"status": "approved"},
            headers=headers,
        )
    prep = client.post(
        f"/api/mdt/runs/{run['id']}/patient-summary", headers=headers
    )
    assert prep.status_code == 202, prep.text
    rel_run = client.post(
        f"/api/mdt/runs/{run['id']}/patient-summary/release", headers=headers
    )
    assert rel_run.status_code == 200, rel_run.text

    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    body = mine.json()
    assert body["summary"]["en"]
    assert body["summary_released_by_name"]
    assert body["visits"][0]["date"] == "2026-10-29"
    assert body["visits"][0]["ready"] is True
    assert body["visits"][0]["en"]
    assert body["visits"][0]["released_by_name"]

    # Staff tokens cannot use the patient summary endpoint.
    denied = client.get("/api/patient-auth/my-summary", headers=headers)
    assert denied.status_code in (401, 403)


def _brief_with_signoff(
    client: TestClient, headers: dict, patient_id: str, approve_all: bool = False
) -> dict:
    run = _ready_brief(client, headers, patient_id)
    for item in run["items"]:
        status = "approved" if approve_all or item == run["items"][0] else "rejected"
        r = client.patch(
            f"/api/mdt/items/{item['id']}", json={"status": status}, headers=headers
        )
        assert r.status_code == 200, r.text
    return run


def test_followup_question_translated_at_ask(client: TestClient, monkeypatch):
    """Staff ask once; the portal reads the question in EN/SW/LG."""
    headers = _headers(client)
    patient_id, token = _patient_token(client, "455455", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    asked = client.post(
        "/api/followups",
        json={"patient_id": patient_id, "question": "Is the headache gone?"},
        headers=headers,
    )
    assert asked.status_code == 201, asked.text
    i18n = asked.json()["question_i18n"]
    assert i18n["en"] == "Is the headache gone?"
    assert i18n["sw"] and i18n["lg"]

    mine = client.get("/api/followups/mine", headers=ph)
    assert mine.json()[0]["question_i18n"]["sw"]


def test_followup_missing_translation_serializes_empty(
    client: TestClient, monkeypatch
):
    """Pre-0021 questions store NULL: endpoints still return 200."""
    from app.db.session import SessionLocal
    from app.followups.models import FollowUp

    headers = _headers(client)
    patient_id, _token = _patient_token(client, "456456", monkeypatch)
    asked = client.post(
        "/api/followups",
        json={"patient_id": patient_id, "question": "How are you?"},
        headers=headers,
    )
    qid = asked.json()["id"]
    db = SessionLocal()
    try:
        db.get(FollowUp, qid).question_i18n = None
        db.commit()
    finally:
        db.close()
    thread = client.get(
        f"/api/followups/for-patient/{patient_id}", headers=headers
    )
    assert thread.status_code == 200, thread.text
    assert thread.json()[0]["question_i18n"] == {}


def test_referral_letter_uses_signed_off_only(client: TestClient):
    """Approved/edited wording in; rejected points and suspicions out."""
    headers = _headers(client)
    patient_id = _patient(client, "457457")
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Fever and cough.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    run = _ready_brief(client, headers, patient_id)
    assert len(run["items"]) >= 2
    first, second = run["items"][0]["id"], run["items"][1]["id"]
    client.patch(f"/api/mdt/items/{first}", json={"status": "approved"}, headers=headers)
    client.patch(
        f"/api/mdt/items/{second}",
        json={"status": "edited", "edited_text": "Doctor wording: continue care."},
        headers=headers,
    )
    letter = client.post(
        f"/api/mdt/runs/{run['id']}/referral-letters",
        json={
            "destination_facility": "Mbarara Hospital",
            "reason": "Uncontrolled pressure",
        },
        headers=headers,
    )
    assert letter.status_code == 201, letter.text
    body = letter.json()
    assert body["summary_status"] == "draft"
    text = body["letter_text"]
    assert "Review ART adherence" in text
    assert "Doctor wording: continue care." in text
    assert "Mbarara Hospital" in text and "Uncontrolled pressure" in text
    assert "present this letter at any health facility" in text
    # Rejected point stays out.
    client.patch(
        f"/api/mdt/items/{first}", json={"status": "rejected"}, headers=headers
    )
    letter2 = client.post(
        f"/api/mdt/runs/{run['id']}/referral-letters",
        json={"destination_facility": "Mbarara Hospital", "reason": "Again"},
        headers=headers,
    )
    assert "Review ART adherence" not in letter2.json()["letter_text"]


def test_referral_letter_requires_signoff(client: TestClient):
    headers = _headers(client)
    patient_id = _patient(client, "458458")
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Routine review.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    run = _ready_brief(client, headers, patient_id)
    denied = client.post(
        f"/api/mdt/runs/{run['id']}/referral-letters",
        json={"destination_facility": "Mbarara Hospital", "reason": "Why"},
        headers=headers,
    )
    assert denied.status_code == 400


def test_referral_letter_release_flow(client: TestClient, monkeypatch):
    """Drafts invisible in the portal; released letters show with text."""
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.mdt.models import ReferralLetter

    headers = _headers(client)
    patient_id, token = _patient_token(client, "459459", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Fever and cough.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    run = _brief_with_signoff(client, headers, patient_id, approve_all=True)
    letter = client.post(
        f"/api/mdt/runs/{run['id']}/referral-letters",
        json={"destination_facility": "Mbarara Hospital", "reason": "Review"},
        headers=headers,
    )
    letter_id = letter.json()["id"]

    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.json()["referral_letters"] == []

    rel = client.post(
        f"/api/mdt/referral-letters/{letter_id}/release", headers=headers
    )
    assert rel.status_code == 200, rel.text
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    letters = mine.json()["referral_letters"]
    assert len(letters) == 1
    assert letters[0]["destination_facility"] == "Mbarara Hospital"
    assert "REFERRAL LETTER" in letters[0]["letter_text"]
    assert letters[0]["released_by_name"]

    # Editing a released letter returns it to draft and hides it again.
    edit = client.patch(
        f"/api/mdt/referral-letters/{letter_id}",
        json={"reason": "Review sooner"},
        headers=headers,
    )
    assert edit.json()["summary_status"] == "draft"
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.json()["referral_letters"] == []

    # Patient hard delete cascades to letters.
    gone = client.delete(f"/api/patients/{patient_id}", headers=headers)
    assert gone.status_code == 200, gone.text
    db = SessionLocal()
    try:
        remaining = db.scalars(
            select(ReferralLetter).where(
                ReferralLetter.patient_id == patient_id
            )
        ).all()
        assert remaining == []
    finally:
        db.close()


def test_visit_summary_written_at_record_time(client: TestClient):
    """Recording a visit drafts its own patient-safe summary in the
    background (inline in tests) — still needing clinician release."""
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
    assert r.json()["summary_status"] == "draft"


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


def test_drafts_hidden_until_released(client: TestClient, monkeypatch):
    """A patient with visits but no releases sees placeholders, never
    draft text — with or without a review on record."""
    headers = _headers(client)
    patient_id, token = _patient_token(client, "451451", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    v = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Headache for three days.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    visit_id = v.json()["id"]
    assert v.json()["summary_status"] == "draft"

    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["run_id"] is None
    assert len(body["visits"]) == 1
    assert body["visits"][0]["ready"] is False
    assert body["visits"][0]["en"] == ""

    rel = client.post(
        f"/api/patients/visits/{visit_id}/release", headers=headers
    )
    assert rel.status_code == 200, rel.text
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    body = mine.json()
    assert body["visits"][0]["ready"] is True
    assert body["visits"][0]["en"]
    assert body["visits"][0]["sw"]
    assert body["visits"][0]["lg"]
    assert body["visits"][0]["released_by_name"]


def test_edit_and_regenerate_reset_release(client: TestClient, monkeypatch):
    """Release is one-way per text version: editing a released summary,
    or regenerating it from new visit content, returns it to draft."""
    headers = _headers(client)
    patient_id, token = _patient_token(client, "454454", monkeypatch)
    ph = {"Authorization": f"Bearer {token}"}
    v = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Headache for three days.", "visit_date": "2026-10-29"},
        headers=headers,
    )
    visit_id = v.json()["id"]
    client.post(f"/api/patients/visits/{visit_id}/release", headers=headers)

    edited = client.patch(
        f"/api/patients/visits/{visit_id}/summary",
        json={"en": "Edited line.", "sw": "Mstari uliohaririwa.", "lg": "Lunyiriri olukyusiddwa."},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["summary_status"] == "draft"
    assert edited.json()["released_by_name"] is None
    assert edited.json()["patient_summary"]["en"] == "Edited line."
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.json()["visits"][0]["ready"] is False

    client.post(f"/api/patients/visits/{visit_id}/release", headers=headers)
    s = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "Malaria RDT positive."},
        headers=headers,
    )
    assert s.status_code == 201, s.text
    record = client.get(f"/api/patients/{patient_id}", headers=headers)
    visit = [x for x in record.json()["visits"] if x["id"] == visit_id][0]
    assert visit["summary_status"] == "draft"
    assert visit["released_by_name"] is None
    mine = client.get("/api/patient-auth/my-summary", headers=ph)
    assert mine.json()["visits"][0]["ready"] is False
