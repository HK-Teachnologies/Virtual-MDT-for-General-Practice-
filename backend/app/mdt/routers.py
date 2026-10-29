import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.mdt.models import (
    ITEM_STATUSES,
    BriefItem,
    BriefRun,
    GuidelineChunk,
    GuidelineDoc,
    Transcription,
)
from app.mdt.schemas import (
    BriefItemRead,
    BriefItemUpdate,
    BriefRequest,
    BriefRunRead,
    GuidelineRead,
    GuidelineUpdate,
    TranscriptionRead,
    TranscriptionUpdate,
)
from app.mdt.tasks import embed_patient_chunks, index_guideline, run_brief, safe_delay
from app.patients.models import Patient
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _run_read(db: Session, run: BriefRun) -> BriefRunRead:
    items = (
        db.scalars(select(BriefItem).where(BriefItem.run_id == run.id)).all()
    )
    return BriefRunRead(
        id=run.id,
        patient_id=run.patient_id,
        status=run.status,
        current_step=run.current_step,
        model=run.model,
        prompt_version=run.prompt_version,
        specialties=list(run.specialties or []),
        error=run.error or "",
        created_at=run.created_at,
        completed_at=run.completed_at,
        patient_summary=dict(run.patient_summary or {}),
        interactions=list(run.interactions or []),
        overdue_checks=list(run.overdue_checks or []),
        items=[
            BriefItemRead(
                id=i.id,
                specialty=i.specialty,
                concern=i.concern,
                citation=i.citation,
                certainty=i.certainty,
                status=i.status,
                edited_text=i.edited_text,
                source_type=i.source_type or "",
                question=i.question or "",
                urgent=bool(i.urgent),
                selfcheck_reason=i.selfcheck_reason or "",
                cited_labels=list(i.cited_labels or []),
            )
            for i in items
        ],
        removed_points=list(run.removed_points or []),
    )


@router.post("/brief", response_model=BriefRunRead, status_code=status.HTTP_202_ACCEPTED)
def request_brief(
    data: BriefRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(Patient, data.patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    run = BriefRun(patient_id=data.patient_id, created_by=current.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    # Patient vectors must exist before retrieval; refresh inline, then brief.
    safe_delay(embed_patient_chunks, data.patient_id)
    safe_delay(run_brief, run.id)
    # Eager/test mode runs the chain inline in another session — re-read
    # so the response reflects the final status, not the queued snapshot.
    db.expire(run)
    return _run_read(db, run)


@router.get("/runs/{run_id}", response_model=BriefRunRead)
def read_run(
    run_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.get(BriefRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    return _run_read(db, run)


@router.get("/patients/{patient_id}/runs", response_model=list[BriefRunRead])
def list_patient_runs(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.scalars(
            select(BriefRun)
            .where(BriefRun.patient_id == patient_id)
            .order_by(BriefRun.created_at.desc())
        ).all()
    )
    return [_run_read(db, run) for run in runs]


@router.patch("/items/{item_id}", response_model=BriefItemRead)
def sign_off_item(
    item_id: str,
    data: BriefItemUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clinician accept/edit/reject of one brief point — persists the sign-off."""
    item = db.get(BriefItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Brief item not found")
    if item.status == "removed":
        raise HTTPException(
            status_code=400,
            detail="This point was removed by the self-check and cannot be signed off",
        )
    if data.status not in ITEM_STATUSES or data.status == "removed":
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of: {', '.join(sorted(ITEM_STATUSES))}",
        )
    item.status = data.status
    item.edited_text = data.edited_text
    db.commit()
    db.refresh(item)
    return BriefItemRead(
        id=item.id,
        specialty=item.specialty,
        concern=item.concern,
        citation=item.citation,
        certainty=item.certainty,
        status=item.status,
        edited_text=item.edited_text,
        source_type=item.source_type or "",
        question=item.question or "",
        urgent=bool(item.urgent),
        selfcheck_reason=item.selfcheck_reason or "",
        cited_labels=list(item.cited_labels or []),
    )


def _guideline_read(db: Session, doc: GuidelineDoc) -> GuidelineRead:
    count = (
        db.scalar(
            select(func.count())
            .select_from(GuidelineChunk)
            .where(GuidelineChunk.doc_id == doc.id)
        )
        or 0
    )
    return GuidelineRead(
        id=doc.id,
        title=doc.title,
        version=doc.version,
        active=doc.active,
        chunks=count,
        index_status=doc.index_status,
        index_error=doc.index_error or "",
    )


@router.post("/guidelines", response_model=GuidelineRead, status_code=status.HTTP_201_CREATED)
def upload_guideline(
    title: str = Form(...),
    version: str = Form(default=""),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store the file and index it in the worker. A 1000+ page PDF takes
    minutes to embed, so this returns immediately with index_status
    "indexing" — the admin page polls until it flips to "ready"."""
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    original = Path(file.filename or "").name
    if not original.lower().endswith((".txt", ".md", ".pdf")):
        raise HTTPException(
            status_code=400, detail="Guidelines must be .pdf, .txt, or .md"
        )
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="File is empty")

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", original) or "guideline"
    stored = f"{uuid.uuid4().hex}_{safe}"
    guide_dir = Path(settings.upload_dir) / "guidelines"
    guide_dir.mkdir(parents=True, exist_ok=True)
    (guide_dir / stored).write_bytes(raw)

    doc = GuidelineDoc(
        title=title,
        version=version,
        created_by=current.id,
        stored_path=str(guide_dir / stored),
        index_status="queued",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    safe_delay(index_guideline, doc.id)
    # Eager/test mode indexed inline above — re-read the final status.
    db.expire(doc)
    return _guideline_read(db, doc)


@router.patch("/guidelines/{doc_id}", response_model=GuidelineRead)
def update_guideline(
    doc_id: str,
    data: GuidelineUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate/deactivate a guideline. Deactivated versions stay stored but
    are excluded from retrieval — how a superseded edition is retired."""
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    doc = db.get(GuidelineDoc, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Guideline not found")
    doc.active = data.active
    db.commit()
    return _guideline_read(db, doc)


@router.post("/guidelines/{doc_id}/reindex", response_model=GuidelineRead)
def reindex_guideline(
    doc_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run indexing for a guideline (e.g. after a failed attempt), without
    re-uploading the file. Stale chunks are cleared by the task itself."""
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    doc = db.get(GuidelineDoc, doc_id)
    if doc is None or not doc.stored_path:
        raise HTTPException(status_code=404, detail="Guideline not found")
    if doc.index_status in ("queued", "indexing"):
        raise HTTPException(status_code=409, detail="Indexing already in progress")
    doc.index_status = "queued"
    doc.index_error = ""
    db.commit()
    safe_delay(index_guideline, doc.id)
    db.expire(doc)
    return _guideline_read(db, doc)


@router.get("/guidelines/{doc_id}/download")
def download_guideline(
    doc_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.get(GuidelineDoc, doc_id)
    if doc is None or not doc.stored_path:
        raise HTTPException(status_code=404, detail="Guideline file not found")
    return FileResponse(
        doc.stored_path,
        media_type="application/octet-stream",
        filename=f"{doc.title}{Path(doc.stored_path).suffix}",
    )


@router.get("/guidelines", response_model=list[GuidelineRead])
def list_guidelines(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    docs = db.scalars(select(GuidelineDoc).order_by(GuidelineDoc.created_at.desc())).all()
    return [_guideline_read(db, doc) for doc in docs]


@router.get("/transcriptions/{attachment_id}", response_model=TranscriptionRead)
def read_transcription(
    attachment_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tr = db.scalar(
        select(Transcription).where(Transcription.attachment_id == attachment_id)
    )
    if tr is None:
        raise HTTPException(status_code=404, detail="No transcription for this file")
    return TranscriptionRead(
        id=tr.id,
        attachment_id=tr.attachment_id,
        kind=tr.kind,
        text=tr.text,
        verified=tr.verified,
        model=tr.model,
    )


@router.patch("/transcriptions/{attachment_id}", response_model=TranscriptionRead)
def update_transcription(
    attachment_id: str,
    data: TranscriptionUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff correction/verification of a machine read (photo, audio, document)."""
    tr = db.scalar(
        select(Transcription).where(Transcription.attachment_id == attachment_id)
    )
    if tr is None:
        raise HTTPException(status_code=404, detail="No transcription for this file")
    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(tr, field, value)
    db.commit()
    db.refresh(tr)
    return TranscriptionRead(
        id=tr.id,
        attachment_id=tr.attachment_id,
        kind=tr.kind,
        text=tr.text,
        verified=tr.verified,
        model=tr.model,
    )


@router.get("/models")
def model_info(current: User = Depends(get_current_user)):
    """Which provider/model the background pipeline will use (no secrets)."""
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "transcribe_model": settings.llm_transcribe_model,
        "embed_model": settings.llm_embed_model,
        "prompt_version": settings.prompt_version,
    }
