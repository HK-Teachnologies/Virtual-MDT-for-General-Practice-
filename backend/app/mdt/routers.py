import re
import uuid
from datetime import datetime, timezone
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
    ReferralLetter,
    Transcription,
)
from app.mdt.schemas import (
    BriefItemRead,
    BriefItemUpdate,
    BriefRequest,
    BriefRunRead,
    GuidelineRead,
    GuidelineUpdate,
    PatientSummaryUpdate,
    ReferralLetterRead,
    ReferralLetterRequest,
    ReferralLetterUpdate,
    TranscriptionRead,
    TranscriptionUpdate,
)
from app.mdt.tasks import (
    embed_patient_chunks,
    index_guideline,
    prepare_patient_summary,
    run_brief,
    safe_delay,
)
from app.patients.models import Patient
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _releaser_name(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return (user.full_name or user.email) if user else None


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
        summary_status=run.summary_status or "draft",
        released_by_name=_releaser_name(db, run.released_by),
        released_at=run.released_at,
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


@router.post(
    "/runs/{run_id}/patient-summary", status_code=status.HTTP_202_ACCEPTED
)
def prepare_run_summary(
    run_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Doctor taps Prepare patient summary after sign-off: draft the
    overall message from approved/edited items only, in the worker."""
    run = db.get(BriefRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    if run.status != "ready":
        raise HTTPException(
            status_code=400, detail="Sign off the brief before preparing the summary"
        )
    safe_delay(prepare_patient_summary, run.id)
    # Eager/test mode prepared inline above — re-read the final state.
    db.expire(run)
    return {"queued": True, "run": _run_read(db, run)}


@router.patch("/runs/{run_id}/patient-summary", response_model=BriefRunRead)
def update_run_summary(
    run_id: str,
    data: PatientSummaryUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clinician edit of the three overall lines. Editing a released
    summary returns it to draft."""
    run = db.get(BriefRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    run.patient_summary = {
        "en": data.en.strip(),
        "sw": data.sw.strip(),
        "lg": data.lg.strip(),
    }
    if (run.summary_status or "draft") == "released":
        run.summary_status = "draft"
        run.released_by = None
        run.released_at = None
    db.commit()
    db.refresh(run)
    return _run_read(db, run)


@router.post("/runs/{run_id}/patient-summary/release", response_model=BriefRunRead)
def release_run_summary(
    run_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Release a draft overall message to the patient portal."""
    run = db.get(BriefRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    if not (run.patient_summary or {}).get("en", "").strip():
        raise HTTPException(status_code=400, detail="No summary to release yet")
    run.summary_status = "released"
    run.released_by = current.id
    run.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _run_read(db, run)


def _age_display(born) -> str:
    if born is None:
        return "adult"
    today = datetime.now(timezone.utc).date()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return f"{age}-year-old"


def _build_referral_letter(
    db: Session,
    run: BriefRun,
    patient: Patient,
    clinician_name: str,
    destination: str,
    reason: str,
    note: str,
) -> str:
    """Deterministic letter from signed-off points only.

    No model call: every clinical word comes from the doctor's notes or
    sign-off. Staff-to-staff, so patient identifiers stay in. The closing
    line covers the common case where the patient presents elsewhere.
    """
    from app.clinics.models import Clinic
    from app.patients.models import Attachment, Visit, VisitSection

    items = db.scalars(select(BriefItem).where(BriefItem.run_id == run.id)).all()
    signed_off = [i for i in items if i.status in ("approved", "edited")]
    visits = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == patient.id)
            .order_by(Visit.visit_date.desc())
        ).all()
    )
    history = []
    for visit in visits[:6]:
        clinic = db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
        sections = db.scalars(
            select(VisitSection).where(VisitSection.visit_id == visit.id)
        ).all()
        parts = [visit.notes.strip()] if visit.notes.strip() else []
        parts += [f"[{s.section}] {s.content.strip()}" for s in sections if s.content.strip()]
        attachments = db.scalars(
            select(Attachment).where(Attachment.visit_id == visit.id)
        ).all()
        for attachment in attachments:
            tr = db.scalar(
                select(Transcription).where(
                    Transcription.attachment_id == attachment.id
                )
            )
            if tr and tr.text.strip():
                tag = "verified" if tr.verified else "UNVERIFIED machine read"
                parts.append(f"attached {tr.kind} ({tag}): {tr.text.strip()}")
        history.append(
            f"{visit.visit_date} ({clinic.name if clinic else 'general'}): "
            + ("; ".join(parts) if parts else "no notes recorded")
        )
    history_lines = [f"- {h}" for h in history] or ["- No visits on record."]
    lines = [
        "REFERRAL LETTER — VIRTUAL MDT",
        f"Date: {datetime.now(timezone.utc).date().isoformat()}",
        f"To: {destination}",
        f"From: {clinician_name} (via Virtual MDT)",
        "",
        f"Re: {patient.full_name}, {_age_display(patient.date_of_birth)}, "
        f"{patient.sex or 'sex not recorded'}, of {patient.district or 'district not recorded'}"
        + (f" ({patient.phone})" if patient.phone else ""),
        "",
        "HISTORY (most recent first):",
        *history_lines,
        "",
        "AGREED FINDINGS AND PLAN (clinician-reviewed):",
    ]
    for item in signed_off:
        text = (
            item.edited_text.strip()
            if item.status == "edited" and item.edited_text
            else item.concern.strip()
        )
        lines.append(f"- [{item.specialty}] {text}")
        if item.question and item.question.strip():
            lines.append(f"  Question: {item.question.strip()}")
    if run.interactions:
        lines += ["", "FLAGGED INTERACTIONS TO CHECK:"]
        for entry in run.interactions or []:
            point = entry.get("point", entry) if isinstance(entry, dict) else entry
            if isinstance(point, dict):
                drugs = " + ".join(point.get("drugs", []))
                lines.append(f"- {drugs + ': ' if drugs else ''}{point.get('concern', '')}")
            else:
                lines.append(f"- {point}")
    if run.overdue_checks:
        lines += ["", "OVERDUE CHECKS:"]
        for entry in run.overdue_checks or []:
            point = entry.get("point", entry) if isinstance(entry, dict) else entry
            if isinstance(point, dict):
                lines.append(
                    f"- {point.get('check', '')}"
                    + (f" (last done: {point.get('last_done')})" if point.get("last_done") else "")
                )
            else:
                lines.append(f"- {point}")
    lines += ["", f"REASON FOR REFERRAL: {reason}"]
    if note:
        lines += ["", f"ADDITIONAL NOTE: {note}"]
    lines += [
        "",
        f"If {patient.full_name.split()[0]} cannot reach {destination}, "
        f"present this letter at any health facility attended.",
    ]
    return "\n".join(lines)


def _letter_read(db: Session, letter: ReferralLetter) -> ReferralLetterRead:
    return ReferralLetterRead(
        id=letter.id,
        run_id=letter.run_id,
        patient_id=letter.patient_id,
        destination_facility=letter.destination_facility,
        reason=letter.reason,
        letter_text=letter.letter_text,
        summary_status=letter.summary_status or "draft",
        released_by_name=_releaser_name(db, letter.released_by),
        released_at=letter.released_at,
        created_at=letter.created_at,
    )


def _get_letter(db: Session, letter_id: str) -> ReferralLetter:
    letter = db.get(ReferralLetter, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail="Referral letter not found")
    return letter


@router.post(
    "/runs/{run_id}/referral-letters",
    response_model=ReferralLetterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_referral_letter(
    run_id: str,
    data: ReferralLetterRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Draft a referral letter from signed-off brief points.

    Deterministic (no model call): every clinical word comes from the
    doctor's notes or sign-off. Starts as draft; the patient sees it in
    the portal only after clinician release, and can present it at any
    facility they end up attending.
    """
    run = db.get(BriefRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    destination = data.destination_facility.strip()
    reason = data.reason.strip()
    if not destination or not reason:
        raise HTTPException(
            status_code=400, detail="Destination facility and reason are required"
        )
    patient = db.get(Patient, run.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    signed_off = (
        db.scalars(
            select(BriefItem).where(
                BriefItem.run_id == run.id,
                BriefItem.status.in_(["approved", "edited"]),
            )
        ).all()
    )
    if not signed_off:
        raise HTTPException(
            status_code=400,
            detail="Sign off at least one brief point before drafting the letter",
        )
    letter = ReferralLetter(
        run_id=run.id,
        patient_id=patient.id,
        destination_facility=destination,
        reason=reason,
        additional_note=data.additional_note.strip(),
        letter_text=_build_referral_letter(
            db,
            run,
            patient,
            current.full_name or current.email,
            destination,
            reason,
            data.additional_note.strip(),
        ),
        created_by=current.id,
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return _letter_read(db, letter)


@router.get("/runs/{run_id}/referral-letters", response_model=list[ReferralLetterRead])
def list_referral_letters(
    run_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.get(BriefRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Brief run not found")
    letters = (
        db.scalars(
            select(ReferralLetter)
            .where(ReferralLetter.run_id == run_id)
            .order_by(ReferralLetter.created_at)
        ).all()
    )
    return [_letter_read(db, letter) for letter in letters]


@router.patch("/referral-letters/{letter_id}", response_model=ReferralLetterRead)
def update_referral_letter(
    letter_id: str,
    data: ReferralLetterUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Correct destination/reason/note and rebuild. Editing a released
    letter returns it to draft."""
    letter = _get_letter(db, letter_id)
    patch = data.model_dump(exclude_unset=True)
    if "destination_facility" in patch:
        letter.destination_facility = (patch["destination_facility"] or "").strip()
    if "reason" in patch:
        letter.reason = (patch["reason"] or "").strip()
    if "additional_note" in patch:
        letter.additional_note = (patch["additional_note"] or "").strip()
    if not letter.destination_facility or not letter.reason:
        raise HTTPException(
            status_code=400, detail="Destination facility and reason are required"
        )
    run = db.get(BriefRun, letter.run_id)
    patient = db.get(Patient, letter.patient_id)
    letter.letter_text = _build_referral_letter(
        db,
        run,
        patient,
        current.full_name or current.email,
        letter.destination_facility,
        letter.reason,
        letter.additional_note,
    )
    if (letter.summary_status or "draft") == "released":
        letter.summary_status = "draft"
        letter.released_by = None
        letter.released_at = None
    db.commit()
    db.refresh(letter)
    return _letter_read(db, letter)


@router.post("/referral-letters/{letter_id}/release", response_model=ReferralLetterRead)
def release_referral_letter(
    letter_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Release a draft letter so the patient can show it at any facility."""
    letter = _get_letter(db, letter_id)
    if not (letter.letter_text or "").strip():
        raise HTTPException(status_code=400, detail="No letter to release yet")
    letter.summary_status = "released"
    letter.released_by = current.id
    letter.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(letter)
    return _letter_read(db, letter)


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
