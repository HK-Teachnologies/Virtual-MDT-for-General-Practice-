from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.mdt.models import BriefItem, BriefRun, PatientChunk, Transcription
from app.patient_auth.models import OtpCode
from app.patients.models import Attachment, Patient, Visit, VisitSection
from app.reviews.models import Review, ReviewRecipient, ReviewResponse
from app.core.config import settings

from .conftest import admin_token


def _staff(client: TestClient, admin: str, email: str, role: str = "doctor"):
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


def _remaining(model, patient_id: str) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.count()).select_from(model).where(model.patient_id == patient_id)
        )


def test_admin_deletes_patient_everything(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    admin = admin_token(client)
    headers = {"Authorization": f"Bearer {admin}"}
    specialist_id, specialist_token = _staff(
        client, admin, "del-specialist@example.com", role="pharmacist"
    )

    r = client.post(
        "/api/patients",
        json={
            "full_name": "Delete Me",
            "phone": "+256700999001",
            "email": "delete-me@example.com",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    patient_id = r.json()["id"]

    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Visit to be deleted", "source": "typed"},
        files=[("files", ("slip.jpg", b"fake-bytes", "image/jpeg"))],
        headers=headers,
    )
    assert r.status_code == 201, r.text
    visit_id = r.json()["id"]
    attachment_id = r.json()["attachments"][0]["id"]
    with SessionLocal() as db:
        stored = db.get(Attachment, attachment_id).stored_path
    assert Path(stored).exists()

    r = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "Hb 12.1"},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    r = client.post("/api/patient-auth/request", json={"identifier": "delete-me@example.com"})
    assert r.status_code == 200, r.text

    r = client.post("/api/mdt/brief", json={"patient_id": patient_id}, headers=headers)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "ready", r.text
    run_id = r.json()["id"]

    r = client.post("/api/specialties", json={"name": "Delete Test Spec"}, headers=headers)
    assert r.status_code == 201, r.text
    spec_id = r.json()["id"]
    r = client.post(
        f"/api/specialties/{spec_id}/members",
        json={"user_id": specialist_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/reviews",
        json={
            "patient_id": patient_id,
            "specialty_ids": [spec_id],
            "message": "Review to be deleted.",
            "brief": {"specialties": [], "items": []},
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    review_id = r.json()["id"]
    r = client.post(
        f"/api/reviews/{review_id}/responses",
        data={"text": "Response to be deleted."},
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 200, r.text

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = client.post(
        f"/api/reviews/{review_id}/responses",
        data={"text": "Image response to be deleted."},
        files=[("image", ("rash.png", png, "image/png"))],
        headers={"Authorization": f"Bearer {specialist_token}"},
    )
    assert r.status_code == 200, r.text
    image_response_id = r.json()["id"]
    with SessionLocal() as db:
        image_stored = db.get(ReviewResponse, image_response_id).image_path
    assert Path(image_stored).exists()

    assert _remaining(Visit, patient_id) == 1
    assert _remaining(PatientChunk, patient_id) >= 1

    r = client.delete(f"/api/patients/{patient_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": True}

    r = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert r.status_code == 404
    listed = client.get("/api/patients", headers=headers).json()
    assert all(p["id"] != patient_id for p in listed)
    assert not Path(stored).exists()
    assert not Path(image_stored).exists()

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Visit).where(Visit.patient_id == patient_id)) == 0
        assert db.scalar(select(func.count()).select_from(VisitSection).where(VisitSection.visit_id == visit_id)) == 0
        assert db.scalar(select(func.count()).select_from(Attachment).where(Attachment.visit_id == visit_id)) == 0
        assert db.scalar(select(func.count()).select_from(Transcription).where(Transcription.attachment_id == attachment_id)) == 0
        assert db.scalar(select(func.count()).select_from(PatientChunk).where(PatientChunk.patient_id == patient_id)) == 0
        assert db.scalar(select(func.count()).select_from(BriefRun).where(BriefRun.patient_id == patient_id)) == 0
        assert db.scalar(select(func.count()).select_from(BriefItem).where(BriefItem.run_id == run_id)) == 0
        assert db.scalar(select(func.count()).select_from(Review).where(Review.patient_id == patient_id)) == 0
        assert db.scalar(select(func.count()).select_from(ReviewRecipient).where(ReviewRecipient.review_id == review_id)) == 0
        assert db.scalar(select(func.count()).select_from(ReviewResponse).where(ReviewResponse.review_id == review_id)) == 0
        assert db.scalar(select(func.count()).select_from(OtpCode).where(OtpCode.patient_id == patient_id)) == 0
        assert db.get(Patient, patient_id) is None


def test_delete_patient_missing_and_forbidden(client: TestClient):
    admin = admin_token(client)
    _, staff_token = _staff(client, admin, "nodelete@example.com")

    r = client.delete(
        "/api/patients/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 404, r.text

    r = client.delete(
        "/api/patients/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r.status_code == 403, r.text

    r = client.delete("/api/patients/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401, r.text
