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
