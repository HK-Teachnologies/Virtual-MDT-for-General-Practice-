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


def test_brief_saves_interactions_and_overdue_checks(client: TestClient):
    """The safety panels persist: a finished run returns non-empty
    structured interactions and overdue checks with the echo provider."""
    token = admin_token(client)
    patient = _patient(client, token, "000005")
    _visit(client, token, patient["id"])

    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": patient["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run

    assert len(run["interactions"]) >= 1
    interaction = run["interactions"][0]
    assert interaction["drugs"] == ["Drug A", "Drug B"]
    assert interaction["concern"]
    assert interaction["source_type"] == "patient_record"

    assert len(run["overdue_checks"]) >= 1
    check = run["overdue_checks"][0]
    assert check["check"] == "Kidney function"
    assert check["last_done"] == "not on record"
    assert check["source_type"] == "patient_record"

    # The GET endpoint returns the same panels.
    r = client.get(
        f"/api/mdt/runs/{run['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["interactions"]) >= 1
    assert len(r.json()["overdue_checks"]) >= 1


def _selfcheck_setup(monkeypatch, draft: dict, verdicts: list[dict] | None):
    """Run the brief chain with a canned model: fixed embeddings plus
    scripted plan/draft/selfcheck replies. Captures the self-check input."""
    from app.core.config import settings
    from app.mdt import tasks

    captured: dict = {}
    monkeypatch.setattr(settings, "llm_provider", "litellm")
    monkeypatch.setattr(tasks.llm, "embed", lambda texts: [[0.1] * 768 for _ in texts])

    def fake_complete_json(*, system: str, user: str, kind: str, **kwargs):
        if kind == "plan":
            return {"specialties": ["HIV care"], "queries": ["q"], "reasoning": "t"}
        if kind == "draft":
            return draft
        if kind == "selfcheck":
            captured["user"] = user
            if verdicts is None:
                raise RuntimeError("model blew up")
            return {"verdicts": verdicts}
        raise AssertionError(f"unexpected kind {kind}")

    monkeypatch.setattr(tasks.llm, "complete_json", fake_complete_json)
    return captured


def _selfcheck_draft() -> dict:
    item = lambda concern: {
        "specialty": "HIV care",
        "concern": concern,
        "question": f"Q: {concern}",
        "citation": "Visit notes on file",
        "source_type": "patient_record",
        "urgent": False,
    }
    return {
        "specialties": ["HIV care"],
        "items": [item("Keep me"), item("Drop me (no verdict)"), item("Drop me (explicit)")],
        "interactions": [
            {
                "drugs": ["Drug A", "Drug B"],
                "concern": "Drop this interaction",
                "citation": "Visit notes on file",
                "source_type": "patient_record",
            }
        ],
        "overdue_checks": [
            {
                "check": "Keep this check",
                "last_done": "not on record",
                "citation": "Visit notes on file",
                "source_type": "patient_record",
            }
        ],
    }


def test_selfcheck_matches_string_ids_and_drops_silent_points(monkeypatch, client: TestClient):
    """String verdict ids match; a point with no verdict is dropped with a
    reason; dropped items persist as removed and cannot be approved."""
    import json

    captured = _selfcheck_setup(
        monkeypatch,
        _selfcheck_draft(),
        [
            {"id": "item-0", "keep": True, "reason": "supported by the visit notes"},
            {"id": "item-2", "keep": False, "reason": "unsupported citation"},
            {"id": "due-0", "keep": True, "reason": "due per record"},
        ],
    )
    token = admin_token(client)
    patient = _patient(client, token, "000006")
    _visit(client, token, patient["id"])
    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": patient["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run

    # The self-check saw JSON points with string ids, not a Python repr.
    payload = json.loads(captured["user"])
    assert [p["id"] for p in payload["points"]] == [
        "item-0",
        "item-1",
        "item-2",
        "int-0",
        "due-0",
    ]
    assert "evidence" in payload

    by_concern = {i["concern"]: i for i in run["items"]}
    assert by_concern["Keep me"]["status"] == "suggested"
    assert by_concern["Keep me"]["question"] == "Q: Keep me"
    assert by_concern["Keep me"]["source_type"] == "patient_record"
    assert by_concern["Drop me (explicit)"]["status"] == "removed"
    assert by_concern["Drop me (explicit)"]["selfcheck_reason"] == "unsupported citation"
    assert by_concern["Drop me (no verdict)"]["status"] == "removed"
    assert by_concern["Drop me (no verdict)"]["selfcheck_reason"] == "no verdict returned"

    # The dropped interaction lands in the audit list, not the panels.
    assert run["interactions"] == []
    assert [rp["kind"] for rp in run["removed_points"]] == ["interaction"]
    assert run["removed_points"][0]["reason"] == "no verdict returned"
    assert len(run["overdue_checks"]) == 1

    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch(
        f"/api/mdt/items/{by_concern['Drop me (explicit)']['id']}",
        json={"status": "approved"},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    r = client.patch(
        f"/api/mdt/items/{by_concern['Keep me']['id']}",
        json={"status": "approved"},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_selfcheck_failure_fails_run(monkeypatch, client: TestClient):
    """If the self-check call itself blows up, the run fails loudly
    instead of keeping unchecked points."""
    _selfcheck_setup(monkeypatch, _selfcheck_draft(), None)
    token = admin_token(client)
    patient = _patient(client, token, "000007")
    _visit(client, token, patient["id"])
    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": patient["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "failed", run
    assert "Self-check failed" in run["error"]


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


def _minimal_pdf(text: str, pages: int = 1) -> bytes:
    kids = " ".join(f"{3 + 2 * p} 0 R" for p in range(pages))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode(),
    ]
    for p in range(pages):
        stream = f"BT /F1 24 Tf 100 700 Td ({text} p{p + 1}) Tj ET".encode()
        objects += [
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {4 + 2 * p} 0 R /Resources << /Font << /F1 {3 + 2 * pages} 0 R >> >> >>".encode(),
            b"<< /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream",
        ]
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
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


def test_guideline_chunks_carry_page_numbers(client: TestClient):
    """A two-page PDF indexes page by page: every chunk knows the source
    page it was cut from, covering both pages."""
    from app.mdt.models import GuidelineChunk

    admin = admin_token(client)
    r = client.post(
        "/api/mdt/guidelines",
        data={"title": "Two page guide", "version": "2024"},
        files={"file": ("two.pdf", _minimal_pdf("Care protocol.", pages=2), "application/pdf")},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["index_status"] == "ready"
    with SessionLocal() as db:
        chunks = (
            db.query(GuidelineChunk)
            .filter(GuidelineChunk.doc_id == r.json()["id"])
            .order_by(GuidelineChunk.chunk_index)
            .all()
        )
    assert len(chunks) >= 2
    assert {c.page_start for c in chunks} == {1, 2}
    assert all(c.page_start == c.page_end for c in chunks)
    assert any("p1" in c.text for c in chunks if c.page_start == 1)
    assert any("p2" in c.text for c in chunks if c.page_start == 2)
    assert all(c.text.startswith("Two page guide (2024):") for c in chunks)


def test_guideline_citation_must_match_retrieved_evidence(monkeypatch, client: TestClient):
    """A guideline-sourced point citing a tag outside this run's evidence
    is dropped with a reason; record-sourced points are unaffected."""
    draft = {
        "specialties": ["HIV care"],
        "items": [
            {
                "specialty": "HIV care",
                "concern": "Invented guideline point",
                "question": "",
                "citation": "[G99] Imaginary Guideline 2099, p. 1",
                "source_type": "guideline",
                "urgent": False,
            },
            {
                "specialty": "HIV care",
                "concern": "Record-based point",
                "question": "",
                "citation": "Visit notes on file",
                "source_type": "patient_record",
                "urgent": False,
            },
        ],
        "interactions": [
            {
                "drugs": ["Drug A", "Drug B"],
                "concern": "Invented interaction",
                "citation": "[G98] Imaginary Guideline 2099, p. 2",
                "source_type": "guideline",
            }
        ],
        "overdue_checks": [],
    }
    _selfcheck_setup(
        monkeypatch,
        draft,
        [
            {"id": "item-0", "keep": True, "reason": "looks supported"},
            {"id": "item-1", "keep": True, "reason": "supported"},
            {"id": "int-0", "keep": True, "reason": "supported"},
        ],
    )
    token = admin_token(client)
    patient = _patient(client, token, "000008")
    _visit(client, token, patient["id"])
    r = client.post(
        "/api/mdt/brief",
        json={"patient_id": patient["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run
    by_concern = {i["concern"]: i for i in run["items"]}
    assert by_concern["Invented guideline point"]["status"] == "removed"
    assert (
        by_concern["Invented guideline point"]["selfcheck_reason"]
        == "cited guideline not in retrieved evidence"
    )
    assert by_concern["Record-based point"]["status"] == "suggested"
    assert by_concern["Record-based point"]["cited_labels"] == []
    assert run["interactions"] == []
    assert [rp["kind"] for rp in run["removed_points"]] == ["interaction"]
    assert (
        run["removed_points"][0]["reason"] == "cited guideline not in retrieved evidence"
    )


def test_plan_constrained_to_clinic_specialties(monkeypatch, client: TestClient):
    """An invented specialty from the model is dropped; a real one matches
    case-insensitively to its canonical spelling, and the plan prompt
    carries the clinic's specialty list."""
    from app.core.config import settings
    from app.mdt import tasks

    captured: dict = {}
    monkeypatch.setattr(settings, "llm_provider", "litellm")
    monkeypatch.setattr(tasks.llm, "embed", lambda texts: [[0.1] * 768 for _ in texts])

    def fake_complete_json(*, system: str, user: str, kind: str, **kwargs):
        if kind == "plan":
            captured["plan_system"] = system
            return {
                "specialties": ["Moon Medicine", "hiv CARE", "HIV care"],
                "queries": [f"query {n}" for n in range(8)],
                "reasoning": "t",
            }
        if kind == "draft":
            return {
                "specialties": ["Moon Medicine"],
                "items": [],
                "interactions": [],
                "overdue_checks": [],
            }
        if kind == "selfcheck":
            return {"verdicts": []}
        raise AssertionError(f"unexpected kind {kind}")

    monkeypatch.setattr(tasks.llm, "complete_json", fake_complete_json)

    token = admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/specialties", json={"name": "HIV care"}, headers=headers
    )
    assert r.status_code == 201, r.text

    patient = _patient(client, token, "000009")
    _visit(client, token, patient["id"])
    r = client.post(
        "/api/mdt/brief", json={"patient_id": patient["id"]}, headers=headers
    )
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "ready", run
    # Invented dropped, case variant canonicalised and de-duplicated, and
    # the draft's invented specialty did not sneak back in.
    assert run["specialties"] == ["HIV care"]
    assert "HIV care" in captured["plan_system"]
    assert "Moon Medicine" not in captured["plan_system"].split("Choose ONLY")[1]


def test_canonical_specialties_unit():
    from app.mdt.tasks import _canonical_specialties

    allowed = ["HIV care", "Cardiology"]
    assert _canonical_specialties(["cardiology", "NCD", " HIV CARE "], allowed) == [
        "Cardiology",
        "HIV care",
    ]
    assert _canonical_specialties("not-a-list", allowed) == []
    assert _canonical_specialties([], allowed) == []


def test_validate_guideline_citation_unit():
    from app.mdt.tasks import _validate_guideline_citation

    tags = {
        "G1": {"label": "Guide A, p. 3", "doc_id": "d1", "page": 3},
        "G2": {"label": "Guide B, p. 7", "doc_id": "d2", "page": 7},
    }
    assert _validate_guideline_citation("[G1] Guide A, p. 3", tags) == [tags["G1"]]
    assert _validate_guideline_citation("[G2] Guide B, p. 7 and [G1] Guide A, p. 3", tags) == [
        tags["G2"],
        tags["G1"],
    ]
    assert _validate_guideline_citation("[G9] Imaginary, p. 1", tags) == []
    assert _validate_guideline_citation("Visit notes on file", tags) == []


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
