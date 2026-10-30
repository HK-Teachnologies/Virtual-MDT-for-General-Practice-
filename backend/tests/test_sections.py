from fastapi.testclient import TestClient

from .conftest import admin_token


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {admin_token(client)}"}


def _patient(client: TestClient, tag: str) -> str:
    r = client.post(
        "/api/patients",
        json={"full_name": f"Section Patient {tag}", "phone": f"+256700000{tag}"},
        headers=_headers(client),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _visit(client: TestClient, patient_id: str) -> str:
    r = client.post(
        f"/api/patients/{patient_id}/visits",
        data={"notes": "Review"},
        headers=_headers(client),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_section_flow(client: TestClient):
    headers = _headers(client)
    patient_id = _patient(client, "011")
    visit_id = _visit(client, patient_id)

    added = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "GeneXpert: MTB detected, rifampicin susceptible."},
        headers=headers,
    )
    assert added.status_code == 201, added.text
    section_id = added.json()["id"]

    bad_type = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "xray", "content": "Nope"},
        headers=headers,
    )
    assert bad_type.status_code == 400

    bad_visit = client.post(
        f"/api/patients/{patient_id}/visits/nope/sections",
        json={"section": "lab", "content": "Nope"},
        headers=headers,
    )
    assert bad_visit.status_code == 404

    edited = client.patch(
        f"/api/patients/sections/{section_id}",
        json={"content": "GeneXpert: MTB detected. Updated note."},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert "Updated note" in edited.json()["content"]

    read = client.get(f"/api/patients/{patient_id}", headers=headers)
    sections = read.json()["visits"][0]["sections"]
    assert len(sections) == 1
    assert sections[0]["section"] == "lab"

    removed = client.delete(
        f"/api/patients/sections/{section_id}", headers=headers
    )
    assert removed.status_code == 200

    gone = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert gone.json()["visits"][0]["sections"] == []

    anon = client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "x"},
    )
    assert anon.status_code == 401


def test_visit_attachments_upload(client: TestClient, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    headers = _headers(client)
    patient_id = _patient(client, "013")
    visit_id = _visit(client, patient_id)

    upload = client.post(
        f"/api/patients/visits/{visit_id}/attachments",
        files=[("files", ("result-slip.jpg", b"fake-image-bytes", "image/jpeg"))],
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["filename"] == "result-slip.jpg"
    attachment_id = body["attachments"][0]["id"]

    download = client.get(
        f"/api/patients/visits/{visit_id}/attachments/{attachment_id}",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"fake-image-bytes"

    empty = client.post(
        f"/api/patients/visits/{visit_id}/attachments",
        headers=headers,
    )
    assert empty.status_code == 400

    missing = client.post(
        "/api/patients/visits/nope/attachments",
        files=[("files", ("x.jpg", b"x", "image/jpeg"))],
        headers=headers,
    )
    assert missing.status_code == 404

    anon = client.post(f"/api/patients/visits/{visit_id}/attachments")
    assert anon.status_code == 401


def test_delete_visit_removes_sections_files_and_reads(
    client: TestClient, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    headers = _headers(client)
    patient_id = _patient(client, "014")
    visit_id = _visit(client, patient_id)
    client.post(
        f"/api/patients/{patient_id}/visits/{visit_id}/sections",
        json={"section": "lab", "content": "CD4 350."},
        headers=headers,
    )
    uploaded = client.post(
        f"/api/patients/visits/{visit_id}/attachments",
        files=[("files", ("slip.png", b"\x89PNG fakepng", "image/png"))],
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["attachments"][0]["id"]

    removed = client.delete(f"/api/patients/visits/{visit_id}", headers=headers)
    assert removed.status_code == 200, removed.text

    read = client.get(f"/api/patients/{patient_id}", headers=headers)
    assert read.json()["visits"] == []

    gone = client.get(
        f"/api/patients/visits/{visit_id}/attachments/{attachment_id}",
        headers=headers,
    )
    assert gone.status_code == 404

    missing = client.delete(
        "/api/patients/visits/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404

    anon = client.delete(f"/api/patients/visits/{visit_id}")
    assert anon.status_code == 401


def test_update_visit(client: TestClient):
    headers = _headers(client)
    patient_id = _patient(client, "012")
    visit_id = _visit(client, patient_id)

    updated = client.patch(
        f"/api/patients/visits/{visit_id}",
        json={"notes": "Revised notes", "visit_date": "2026-02-20"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "Revised notes"
    assert updated.json()["visit_date"] == "2026-02-20"

    bad_date = client.patch(
        f"/api/patients/visits/{visit_id}",
        json={"visit_date": "yesterday"},
        headers=headers,
    )
    assert bad_date.status_code == 400
