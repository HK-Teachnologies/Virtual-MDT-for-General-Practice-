from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.mdt.models import PatientChunk

from .conftest import admin_token


def _patient(client: TestClient, token: str, tag: str) -> dict:
    r = client.post(
        "/api/patients",
        json={
            "full_name": f"MDT Patient {tag}",
            "phone": f"+256711{tag}",
            "email": f"mdt-{tag}@example.com",
            "sex": "Female",
            "district": "Wakiso",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _visit(client: TestClient, token: str, patient_id: str) -> dict:
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={
            "notes": "Cough for three weeks, night sweats, on ART since 2021.",
            "source": "typed",
            "visit_date": "2026-10-20",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_brief_flow_end_to_end(client: TestClient):
    token = admin_token(client)
    patient = _patient(client, token, "000001")
    _visit(client, token, patient["id"])

    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": patient["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    # Eager test mode runs the whole chain inline: plan, retrieve, draft, check.
    assert run["status"] == "ready", run
    assert len(run["items"]) == 2
    assert {i["status"] for i in run["items"]} == {"suggested"}

    r = client.get(
        f"/api/mdt/runs/{run['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"

    # Clinician sign-off persists.
    item_id = run["items"][0]["id"]
    r = client.patch(
        f"/api/mdt/items/{item_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    r = client.get(
        f"/api/mdt/patients/{patient['id']}/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


def test_brief_chunks_indexed(client: TestClient):
    token = admin_token(client)
    patient = _patient(client, token, "000002")
    _visit(client, token, patient["id"])
    with SessionLocal() as db:
        chunks = (
            db.query(PatientChunk)
            .filter(PatientChunk.patient_id == patient["id"])
            .all()
        )
    assert len(chunks) >= 1


def test_brief_unknown_patient(client: TestClient):
    token = admin_token(client)
    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_brief_requires_staff_login(client: TestClient):
    r = client.post("/api/mdt/brief", json={"patient_id": "x"})
    assert r.status_code == 401


def _staff_token(client: TestClient, admin: str, email: str) -> str:
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "staff12345",
            "full_name": "Staff",
            "role": "clinical_officer",
        },
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": "staff12345"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_guidelines_admin_only(client: TestClient):
    admin = admin_token(client)
    staff = _staff_token(client, admin, "mdt-staff@example.com")
    files = {"file": ("guide.txt", b"Give ART daily. Monitor adherence.", "text/plain")}

    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "HIV quick ref", "version": "2024"},
        files=files,
        headers={"Authorization": f"Bearer {staff}"},
    )
    assert r.status_code == 403, r.text

    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "HIV quick ref", "version": "2024"},
        files=files,
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["chunks"] >= 1

    r = client.get(
        "/api/mdt/guidelines", headers={"Authorization": f"Bearer {staff}"}
    )
    assert r.status_code == 200, r.text
    assert any(d["title"] == "HIV quick ref" for d in r.json())


def _minimal_pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return pdf


def test_guideline_pdf_upload_and_retire(client: TestClient):
    admin = admin_token(client)
    files = {"file": ("hiv-guide.pdf", _minimal_pdf("Give ART daily."), "application/pdf")}
    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "HIV PDF guide", "version": "2024"},
        files=files,
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["chunks"] >= 1
    assert doc["index_status"] == "ready"

    # Original file is kept for download.
    r = client.get(
        f"/api/mdt/guidelines/{doc['id']}/download",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")

    # Retire then reactivate.
    for active, label in [(False, "Retired"), (True, "Active")]:
        r = client.patch(
            f"/api/mdt/guidelines/{doc['id']}",
            json={"active": active},
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["active"] is active

    # Non-document uploads are rejected.
    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "Bad", "version": ""},
        files={"file": ("x.png", b"\x89PNG", "image/png")},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 400, r.text


def test_guideline_indexing_batches_embeddings(monkeypatch, client: TestClient):
    """A long document embeds in bounded batches, not one giant call."""
    from app.core.config import settings
    from app.mdt import tasks

    calls: list[int] = []
    real_embed = tasks.llm.embed

    def counting(texts: list[str]):
        calls.append(len(texts))
        return real_embed(texts)

    monkeypatch.setattr(tasks.llm, "embed", counting)
    monkeypatch.setattr(settings, "llm_embed_batch", 2)

    admin = admin_token(client)
    body = "\n\n".join(f"Section {i}. " + ("Care protocol. " * 60) for i in range(20))
    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "Long guide", "version": "2024"},
        files={"file": ("long.txt", body.encode(), "text/plain")},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["index_status"] == "ready"
    assert doc["chunks"] > 2
    assert len(calls) > 1
    assert max(calls) <= 2
    assert sum(calls) == doc["chunks"]


def test_guideline_reindex_recovers_and_dedupes(client: TestClient):
    from app.mdt.models import GuidelineChunk

    admin = admin_token(client)
    headers = {"Authorization": f"Bearer {admin}"}
    body = "Reindex me. " * 200
    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "Reindex guide", "version": "2024"},
        files={"file": ("reindex.txt", body.encode(), "text/plain")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert r.json()["index_status"] == "ready"
    with SessionLocal() as db:
        first = db.query(GuidelineChunk).filter(GuidelineChunk.doc_id == doc_id).count()
        db.add(
            GuidelineChunk(
                doc_id=doc_id, chunk_index=9999, text="stale", embedding=[0.1] * 768
            )
        )
        db.commit()
    assert first >= 1

    r = client.post(f"/api/mdt/guidelines/{doc_id}/reindex", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["index_status"] == "ready"
    with SessionLocal() as db:
        rows = db.query(GuidelineChunk).filter(GuidelineChunk.doc_id == doc_id).all()
    assert all(c.chunk_index != 9999 for c in rows)
    assert len(rows) == first

    # Non-admins cannot reindex; unknown docs 404.
    staff = _staff_token(client, admin, "reindex-staff@example.com")
    r = client.post(
        f"/api/mdt/guidelines/{doc_id}/reindex",
        headers={"Authorization": f"Bearer {staff}"},
    )
    assert r.status_code == 403, r.text
    r = client.post(
        "/api/mdt/guidelines/00000000-0000-0000-0000-000000000000/reindex",
        headers=headers,
    )
    assert r.status_code == 404, r.text


def test_retrieval_skips_half_indexed_guides(client: TestClient):
    from sqlalchemy import select

    from app.mdt import retrieval
    from app.mdt.models import GuidelineChunk, GuidelineDoc
    from app.users.models import User

    admin = admin_token(client)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        doc = GuidelineDoc(
            title="Half indexed",
            version="",
            created_by=user.id,
            active=True,
            index_status="indexing",
        )
        db.add(doc)
        db.flush()
        db.add(
            GuidelineChunk(
                doc_id=doc.id, chunk_index=0, text="Give ART daily.", embedding=[0.1] * 1536
            )
        )
        db.commit()
        doc_id = doc.id
        found = retrieval.retrieve_guidelines(db, query_vector=[0.1] * 1536, k=8)
    # Other tests' fully-indexed guides may match — the half-indexed doc must not.
    assert all(c.doc_id != doc_id for c in found)


def test_patient_record_ingestion(client: TestClient):
    """Voice (audio), photo (image), and document uploads each get a machine
    read nested on the visit, which staff can correct and verify."""
    token = admin_token(client)
    patient = _patient(client, token, "000003")
    wav = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x40\x1f\x00\x00\x40\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"
    )
    r = client.post(
        f"/api/patients/{patient['id']}/visits",
        data={"notes": "Review visit.", "visit_date": "2026-10-21"},
        files=[
            ("files", ("lab.txt", b"CD4 350, viral load suppressed.", "text/plain")),
            ("files", ("consult.wav", wav, "audio/wav")),
            ("files", ("slip.png", b"\x89PNG fakepng", "image/png")),
        ],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text

    r = client.get(
        f"/api/patients/{patient['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    attachments = r.json()["visits"][0]["attachments"]
    kinds = {a["filename"]: (a["transcription"] or {}).get("kind") for a in attachments}
    assert kinds == {
        "lab.txt": "document",
        "consult.wav": "audio",
        "slip.png": "image",
    }
    doc_text = next(
        a["transcription"]["text"] for a in attachments if a["filename"] == "lab.txt"
    )
    assert "CD4 350" in doc_text
    for a in attachments:
        assert a["transcription"]["verified"] is False

    # Staff corrects and verifies one read.
    lab = next(a for a in attachments if a["filename"] == "lab.txt")
    r = client.patch(
        f"/api/mdt/transcriptions/{lab['id']}",
        json={"text": "CD4 350, viral load suppressed. Verified.", "verified": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True
    assert "Verified." in r.json()["text"]

    r = client.patch(
        f"/api/mdt/transcriptions/{lab['id']}", json={"verified": True}
    )
    assert r.status_code == 401


def test_audio_detected_by_extension(client: TestClient):
    """Voice notes stay audio even when the uploader labels them octet-stream."""
    token = admin_token(client)
    patient = _patient(client, token, "000004")
    r = client.post(
        f"/api/patients/{patient['id']}/visits",
        data={"notes": "Voice note visit.", "visit_date": "2026-10-22"},
        files=[("files", ("note.wav", b"RIFF fakery", "application/octet-stream"))],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    r = client.get(
        f"/api/patients/{patient['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    attachments = r.json()["visits"][0]["attachments"]
    assert attachments[0]["transcription"]["kind"] == "audio"


def test_model_info(client: TestClient):
    token = admin_token(client)
    r = client.get(
        "/api/mdt/models", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "echo"
    assert "api_key" not in r.text.lower()
