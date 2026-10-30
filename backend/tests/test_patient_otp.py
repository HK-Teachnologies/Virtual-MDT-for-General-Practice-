from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.patient_auth.models import OtpCode

from .conftest import admin_token


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {admin_token(client)}"}


def _make_patient(client: TestClient, tag: str) -> str:
    r = client.post(
        "/api/patients",
        json={
            "full_name": f"OTP Patient {tag}",
            "email": f"otp-{tag}@example.com",
            "phone": f"+256700{tag}",
        },
        headers=_headers(client),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_otp_code_logged_for_dev_lookup(client: TestClient, monkeypatch, caplog):
    """The code is logged server-side so made-up demo addresses can still
    sign in (gated by OTP_LOG_CODE)."""
    import logging

    from app.core.config import settings

    monkeypatch.setattr("secrets.randbelow", lambda n: 643590)
    monkeypatch.setattr(settings, "otp_log_code", True)
    _make_patient(client, "999999")
    with caplog.at_level(logging.INFO, logger="app.patient_auth.routers"):
        sent = client.post(
            "/api/patient-auth/request", json={"identifier": "otp-999999@example.com"}
        )
    assert sent.status_code == 200
    assert "OTP for otp-999999@example.com: 743590" in caplog.text

    monkeypatch.setattr(settings, "otp_log_code", False)
    with caplog.at_level(logging.INFO, logger="app.patient_auth.routers"):
        caplog.clear()
        client.post(
            "/api/patient-auth/request", json={"identifier": "otp-999999@example.com"}
        )
    assert "743590" not in caplog.text


def _portal_token(client: TestClient, monkeypatch, tag: str) -> str:
    monkeypatch.setattr("secrets.randbelow", lambda n: 643590)
    _make_patient(client, tag)
    client.post(
        "/api/patient-auth/request", json={"identifier": f"otp-{tag}@example.com"}
    )
    ok = client.post(
        "/api/patient-auth/verify",
        json={"identifier": f"otp-{tag}@example.com", "code": "743590"},
    )
    assert ok.status_code == 200, ok.text
    return ok.json()["access_token"]


def test_portal_chat_guides_without_diagnosing(
    client: TestClient, monkeypatch
):
    """Patient guide chat: plain answers from released content, urgent
    redirect for danger signs, voice notes transcribed first."""
    from .conftest import admin_token

    token = _portal_token(client, monkeypatch, "777777")
    ph = {"Authorization": f"Bearer {token}"}

    asked = client.post(
        "/api/patient-auth/chat",
        data={"message": "Which clinic should I visit for a headache?", "lang": "en"},
        headers=ph,
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["reply"] == "Echo clinic guide reply."
    assert body["urgent"] is False
    assert body["lang"] == "en"

    urgent = client.post(
        "/api/patient-auth/chat",
        data={"message": "There is heavy bleeding", "lang": "sw"},
        headers=ph,
    )
    assert urgent.status_code == 200, urgent.text
    assert urgent.json()["urgent"] is True
    assert "dharura" in urgent.json()["reply"]

    urgent_lg = client.post(
        "/api/patient-auth/chat",
        data={"message": "There is heavy bleeding", "lang": "lg"},
        headers=ph,
    )
    assert urgent_lg.status_code == 200, urgent_lg.text
    assert urgent_lg.json()["urgent"] is True
    assert "akabenje" in urgent_lg.json()["reply"]

    wav = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x40\x1f\x00\x00\x40\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"
    )
    voice = client.post(
        "/api/patient-auth/chat",
        data={"lang": "lg"},
        files=[("audio", ("q.wav", wav, "audio/wav"))],
        headers=ph,
    )
    assert voice.status_code == 200, voice.text
    assert voice.json()["question_original"] == "Echo transcript."
    assert voice.json()["reply"] == "Echo clinic guide reply."

    empty = client.post(
        "/api/patient-auth/chat", data={"message": " ", "lang": "en"}, headers=ph
    )
    assert empty.status_code == 400

    bad_lang = client.post(
        "/api/patient-auth/chat", data={"message": "hi", "lang": "xx"}, headers=ph
    )
    assert bad_lang.status_code == 400

    staff = client.post(
        "/api/patient-auth/chat",
        data={"message": "hi", "lang": "en"},
        headers={"Authorization": f"Bearer {admin_token(client)}"},
    )
    assert staff.status_code in (401, 403)

    anon = client.post("/api/patient-auth/chat", data={"message": "hi"})
    assert anon.status_code in (401, 403)


def test_answer_notification_is_signin_nudge_only(client: TestClient, monkeypatch):
    """Answer email: sign-in nudge with no clinical content; silent in dev."""
    from app.patient_auth import routers as pa

    captured: dict = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(pa.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(pa.settings, "smtp_host", "mail.example.com")
    assert pa.send_answer_notification("patient@example.com") is True
    message = captured["message"]
    assert message["To"] == "patient@example.com"
    assert "answered" in message["Subject"].lower()
    body = message.get_content()
    assert "Sign in" in body
    assert "Monday at 9" not in body

    monkeypatch.setattr(pa.settings, "smtp_host", "")
    assert pa.send_answer_notification("patient@example.com") is False


def test_otp_flow(client: TestClient, monkeypatch):
    # Fixed code: randbelow(900000) -> 643590, so the code is "743590".
    monkeypatch.setattr("secrets.randbelow", lambda n: 643590)
    _make_patient(client, "111111")

    unknown = client.post(
        "/api/patient-auth/request", json={"identifier": "nobody@example.com"}
    )
    assert unknown.status_code == 200  # generic answer, no enumeration

    sent = client.post(
        "/api/patient-auth/request", json={"identifier": "otp-111111@example.com"}
    )
    assert sent.status_code == 200

    wrong = client.post(
        "/api/patient-auth/verify",
        json={"identifier": "otp-111111@example.com", "code": "000000"},
    )
    assert wrong.status_code == 401

    ok = client.post(
        "/api/patient-auth/verify",
        json={"identifier": "otp-111111@example.com", "code": "743590"},
    )
    assert ok.status_code == 200, ok.text
    token = ok.json()["access_token"]

    me = client.get(
        "/api/patient-auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "otp-111111@example.com"

    reuse = client.post(
        "/api/patient-auth/verify",
        json={"identifier": "otp-111111@example.com", "code": "743590"},
    )
    assert reuse.status_code == 401


def test_otp_expiry_and_lockout(client: TestClient, monkeypatch):
    monkeypatch.setattr("secrets.randbelow", lambda n: 111111)
    patient_222 = _make_patient(client, "222222")
    client.post(
        "/api/patient-auth/request", json={"identifier": "otp-222222@example.com"}
    )

    db = SessionLocal()
    try:
        code = db.scalar(
            select(OtpCode)
            .where(OtpCode.patient_id == patient_222)
            .order_by(OtpCode.created_at.desc())
        )
        assert code is not None
        code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    expired = client.post(
        "/api/patient-auth/verify",
        json={"identifier": "otp-222222@example.com", "code": "211111"},
    )
    assert expired.status_code == 401

    _make_patient(client, "333333")
    client.post(
        "/api/patient-auth/request", json={"identifier": "otp-333333@example.com"}
    )
    for _ in range(5):
        client.post(
            "/api/patient-auth/verify",
            json={"identifier": "otp-333333@example.com", "code": "000000"},
        )
    locked = client.post(
        "/api/patient-auth/verify",
        json={"identifier": "otp-333333@example.com", "code": "211111"},
    )
    assert locked.status_code == 401
