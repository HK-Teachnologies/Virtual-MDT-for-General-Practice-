import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.clinics.models import Clinic
from app.patients.models import SECTION_TYPES, Attachment, Patient, Visit, VisitSection
from app.patients.schemas import (
    PatientCreate,
    PatientRead,
    PatientUpdate,
    SectionCreate,
    SectionRead,
    SectionUpdate,
    VisitRead,
    VisitSummaryUpdate,
    VisitUpdate,
)
from app.mdt.models import (
    BriefItem,
    BriefRun,
    PatientChunk,
    ReferralLetter,
    Transcription,
)
from app.mdt.tasks import (
    embed_patient_chunks,
    safe_delay,
    summarize_visit,
    transcribe_attachment,
)
from app.followups.models import FollowUp
from app.patient_auth.models import OtpCode
from app.reviews.models import Review, ReviewRecipient, ReviewResponse
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _safe_filename(name: str) -> str:
    stem = Path(name).name
    return re.sub(r"[^A-Za-z0-9_.-]", "_", stem) or "upload"


def _with_transcriptions(db: Session, attachments: list[Attachment]) -> None:
    """Attach each file's machine read (if any) for the nested API shape."""
    if not attachments:
        return
    rows = (
        db.scalars(
            select(Transcription).where(
                Transcription.attachment_id.in_([a.id for a in attachments])
            )
        ).all()
    )
    by_attachment = {t.attachment_id: t for t in rows}
    for attachment in attachments:
        attachment.transcription = by_attachment.get(attachment.id)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    data: PatientCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_measurements(data.weight_kg, data.height_cm)
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
        phone=data.phone,
        email=data.email,
        district=data.district,
        address=data.address,
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        created_by=current.id,
    )
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Phone or email already registered")
    db.refresh(patient)
    patient.visit_count = 0
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = db.execute(
        select(Patient, func.count(Visit.id))
        .outerjoin(Visit, Visit.patient_id == Patient.id)
        .group_by(Patient.id)
        .order_by(Patient.created_at.desc())
    ).all()
    ids = [patient.id for patient, _ in rows]
    open_counts: dict[str, int] = {}
    unverified_counts: dict[str, int] = {}
    if ids:
        open_counts = dict(
            db.execute(
                select(Review.patient_id, func.count(Review.id))
                .where(Review.patient_id.in_(ids), Review.status != "closed")
                .group_by(Review.patient_id)
            ).all()
        )
        unverified_counts = dict(
            db.execute(
                select(Visit.patient_id, func.count(Transcription.id))
                .join(Attachment, Attachment.visit_id == Visit.id)
                .join(Transcription, Transcription.attachment_id == Attachment.id)
                .where(Visit.patient_id.in_(ids), Transcription.verified.is_(False))
                .group_by(Visit.patient_id)
            ).all()
        )
    patients = []
    for patient, visit_count in rows:
        patient.visit_count = visit_count
        patient.open_review_count = open_counts.get(patient.id, 0)
        patient.unverified_read_count = unverified_counts.get(patient.id, 0)
        patients.append(patient)
    return patients


def _release_names(db: Session, user_ids: set[str]) -> dict[str, str]:
    """Staff full names for release labels; unknown ids stay blank."""
    ids = {i for i in user_ids if i}
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: (u.full_name or u.email) for u in rows}


def load_patient_detail(db: Session, patient_id: str) -> Patient:
    """Full patient record with visits and attachments, or 404."""
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    visits = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date.desc())
        ).all()
    )
    names = _release_names(db, {v.released_by for v in visits if v.released_by})
    for visit in visits:
        _populate_visit(db, visit)
        visit.released_by_name = names.get(visit.released_by or "")
    _set_creator_names(db, list(visits))
    patient.visits = visits
    patient.visit_count = len(visits)
    patient.unverified_read_count = sum(
        1
        for visit in visits
        for a in visit.attachments
        if a.transcription and not a.transcription.verified
    )
    patient.open_review_count = (
        db.scalar(
            select(func.count(Review.id)).where(
                Review.patient_id == patient_id, Review.status != "closed"
            )
        )
        or 0
    )
    return patient


def _populate_visit(db: Session, visit: Visit) -> None:
    """Nested record shape for one visit (attachments, clinic, sections)."""
    visit.attachments = (
        db.scalars(select(Attachment).where(Attachment.visit_id == visit.id)).all()
    )
    _with_transcriptions(db, visit.attachments)
    visit.clinic = (
        db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
    )
    visit.sections = (
        db.scalars(
            select(VisitSection)
            .where(VisitSection.visit_id == visit.id)
            .order_by(VisitSection.created_at)
        ).all()
    )


def _set_creator_names(db: Session, visits: list[Visit]) -> None:
    """Staff display names for the audit trail: who recorded each visit,
    section, and file. Unknown ids stay blank."""
    ids = {v.created_by for v in visits if v.created_by}
    for visit in visits:
        ids.update(s.created_by for s in visit.sections if s.created_by)
        ids.update(a.created_by for a in visit.attachments if a.created_by)
    names = _release_names(db, ids)
    for visit in visits:
        visit.created_by_name = names.get(visit.created_by or "")
        for section in visit.sections:
            section.created_by_name = names.get(section.created_by or "")
        for attachment in visit.attachments:
            attachment.created_by_name = names.get(attachment.created_by or "")


@router.get("/{patient_id}", response_model=PatientRead)
def read_patient(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return load_patient_detail(db, patient_id)


def _check_measurements(weight_kg: float | None, height_cm: float | None) -> None:
    for label, value, lo, hi in (
        ("weight_kg", weight_kg, 0, 500),
        ("height_cm", height_cm, 0, 300),
    ):
        if value is not None and not (lo < value <= hi):
            raise HTTPException(
                status_code=400,
                detail=f"{label} must be between {lo} and {hi} (or omitted)",
            )


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: str,
    data: PatientUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff edit of patient details and optional measurements."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    patch = data.model_dump(exclude_unset=True)
    _check_measurements(patch.get("weight_kg"), patch.get("height_cm"))
    for field, value in patch.items():
        setattr(patient, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Phone or email already registered")
    db.refresh(patient)
    return load_patient_detail(db, patient_id)


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only full removal: visits, sections, files, vectors, brief
    runs, reviews, and login codes — nothing orphaned, files off disk."""
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    file_paths: list[str] = []

    visit_ids = db.scalars(
        select(Visit.id).where(Visit.patient_id == patient_id)
    ).all()
    if visit_ids:
        attachments = db.scalars(
            select(Attachment).where(Attachment.visit_id.in_(visit_ids))
        ).all()
        file_paths.extend(a.stored_path for a in attachments)
        attachment_ids = [a.id for a in attachments]
        if attachment_ids:
            db.execute(
                delete(Transcription).where(
                    Transcription.attachment_id.in_(attachment_ids)
                )
            )
            db.execute(
                delete(Attachment).where(Attachment.id.in_(attachment_ids))
            )
        db.execute(
            delete(VisitSection).where(VisitSection.visit_id.in_(visit_ids))
        )
        db.execute(delete(Visit).where(Visit.id.in_(visit_ids)))

    db.execute(
        delete(PatientChunk).where(PatientChunk.patient_id == patient_id)
    )

    run_ids = db.scalars(
        select(BriefRun.id).where(BriefRun.patient_id == patient_id)
    ).all()
    if run_ids:
        db.execute(delete(BriefItem).where(BriefItem.run_id.in_(run_ids)))
        db.execute(delete(BriefRun).where(BriefRun.id.in_(run_ids)))
    db.execute(
        delete(ReferralLetter).where(ReferralLetter.patient_id == patient_id)
    )

    review_ids = db.scalars(
        select(Review.id).where(Review.patient_id == patient_id)
    ).all()
    if review_ids:
        voices = db.scalars(
            select(ReviewResponse).where(ReviewResponse.review_id.in_(review_ids))
        ).all()
        file_paths.extend(v.audio_path for v in voices if v.audio_path)
        file_paths.extend(v.image_path for v in voices if v.image_path)
        db.execute(
            delete(ReviewResponse).where(ReviewResponse.review_id.in_(review_ids))
        )
        db.execute(
            delete(ReviewRecipient).where(ReviewRecipient.review_id.in_(review_ids))
        )
        db.execute(delete(Review).where(Review.id.in_(review_ids)))

    db.execute(delete(OtpCode).where(OtpCode.patient_id == patient_id))
    followup_audio = db.scalars(
        select(FollowUp).where(FollowUp.patient_id == patient_id)
    ).all()
    file_paths.extend(f.answer_audio_path for f in followup_audio if f.answer_audio_path)
    db.execute(delete(FollowUp).where(FollowUp.patient_id == patient_id))
    db.delete(patient)
    db.commit()

    for path in file_paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            continue
    return {"deleted": True}


@router.post("/{patient_id}/visits", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
def add_visit(
    patient_id: str,
    notes: str = Form(default=""),
    source: str = Form(default="typed"),
    visit_date: str = Form(default=""),
    clinic_id: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    try:
        parsed_date = date.fromisoformat(visit_date) if visit_date else date.today()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="visit_date must be YYYY-MM-DD"
        )

    clinic = None
    if clinic_id:
        clinic = db.get(Clinic, clinic_id)
        if clinic is None or not clinic.active:
            raise HTTPException(status_code=400, detail="Unknown clinic")

    visit = Visit(
        patient_id=patient_id,
        visit_date=parsed_date,
        notes=notes,
        source=source or "typed",
        clinic_id=clinic.id if clinic else None,
        created_by=current.id,
    )
    db.add(visit)
    db.flush()

    attachments = _store_uploads(db, visit.id, files, current.id)

    db.commit()
    db.refresh(visit)
    visit.attachments = attachments
    _with_transcriptions(db, attachments)
    visit.clinic = clinic
    visit.sections = []
    _set_creator_names(db, [visit])
    # Background AI: read uploaded photos/audio, refresh patient vectors,
    # and write the patient-safe visit summary for the portal.
    for attachment in attachments:
        safe_delay(transcribe_attachment, attachment.id)
    safe_delay(embed_patient_chunks, patient_id)
    safe_delay(summarize_visit, visit.id)
    # The summary task commits in its own session: reload so the response
    # carries it when tasks run inline (tests), and stays honest ({}) when
    # the worker has not finished yet (production polling/backfill).
    db.expire(visit, ["patient_summary"])
    return visit


def _store_uploads(
    db: Session, visit_id: str, files: list[UploadFile], user_id: str
) -> list[Attachment]:
    """Persist uploaded files as visit attachments. Skips empty parts."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    attachments = []
    for upload in files:
        if not upload.filename:
            continue
        stored = f"{uuid.uuid4().hex}_{_safe_filename(upload.filename)}"
        path = upload_dir / stored
        with path.open("wb") as out:
            out.write(upload.file.read())
        attachment = Attachment(
            visit_id=visit_id,
            filename=Path(upload.filename).name,
            stored_path=str(path),
            content_type=upload.content_type,
            created_by=user_id,
        )
        db.add(attachment)
        attachments.append(attachment)
    return attachments


@router.post("/visits/{visit_id}/attachments", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
def add_visit_attachments(
    visit_id: str,
    files: list[UploadFile] = File(default=[]),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach photos, dictations, or documents to an existing visit.

    Used by the Add Result form so lab/imaging notes can carry a picture
    of the slip or a recorded dictation. Every file gets the same
    background AI read as capture-time uploads."""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    attachments = _store_uploads(db, visit.id, files, current.id)
    if not attachments:
        raise HTTPException(status_code=400, detail="No files uploaded")
    db.commit()
    db.refresh(visit)
    for attachment in attachments:
        safe_delay(transcribe_attachment, attachment.id)
    safe_delay(embed_patient_chunks, visit.patient_id)
    safe_delay(summarize_visit, visit.id)
    _populate_visit(db, visit)
    _name_visit(db, visit)
    _set_creator_names(db, [visit])
    return visit


@router.get("/visits/{visit_id}/attachments/{attachment_id}")
def download_attachment(
    visit_id: str,
    attachment_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.visit_id == visit_id
        )
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(
        attachment.stored_path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=attachment.filename,
    )


def _get_visit(db: Session, patient_id: str, visit_id: str) -> Visit:
    visit = db.scalar(
        select(Visit).where(Visit.id == visit_id, Visit.patient_id == patient_id)
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.post(
    "/{patient_id}/visits/{visit_id}/sections",
    response_model=SectionRead,
    status_code=status.HTTP_201_CREATED,
)
def add_section(
    patient_id: str,
    visit_id: str,
    data: SectionCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = _get_visit(db, patient_id, visit_id)
    if data.section not in SECTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"section must be one of: {', '.join(sorted(SECTION_TYPES))}",
        )
    section = VisitSection(
        visit_id=visit.id,
        section=data.section,
        content=data.content,
        created_by=current.id,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    section.created_by_name = _release_names(db, {section.created_by}).get(
        section.created_by or ""
    )
    safe_delay(embed_patient_chunks, patient_id)
    safe_delay(summarize_visit, visit.id)
    return section


@router.patch("/sections/{section_id}", response_model=SectionRead)
def update_section(
    section_id: str,
    data: SectionUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    section = db.get(VisitSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    visit = db.get(Visit, section.visit_id)
    patch = data.model_dump(exclude_unset=True)
    if "section" in patch and patch["section"] not in SECTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"section must be one of: {', '.join(sorted(SECTION_TYPES))}",
        )
    for field, value in patch.items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    if visit is not None:
        safe_delay(embed_patient_chunks, visit.patient_id)
        safe_delay(summarize_visit, visit.id)
    return section


@router.delete("/visits/{visit_id}")
def delete_visit(
    visit_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove one visit with its sections, files, and machine reads.

    Files leave the disk too; nothing orphaned. Use for duplicate or
    mistaken captures — the whole patient stays intact."""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    patient_id = visit.patient_id
    attachments = db.scalars(
        select(Attachment).where(Attachment.visit_id == visit.id)
    ).all()
    file_paths = [a.stored_path for a in attachments]
    attachment_ids = [a.id for a in attachments]
    if attachment_ids:
        db.execute(
            delete(Transcription).where(
                Transcription.attachment_id.in_(attachment_ids)
            )
        )
        db.execute(delete(Attachment).where(Attachment.id.in_(attachment_ids)))
    db.execute(delete(VisitSection).where(VisitSection.visit_id == visit.id))
    db.delete(visit)
    db.commit()
    for path in file_paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            continue
    safe_delay(embed_patient_chunks, patient_id)
    return {"deleted": True}


@router.delete("/sections/{section_id}")
def delete_section(
    section_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    section = db.get(VisitSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    visit = db.get(Visit, section.visit_id)
    db.delete(section)
    db.commit()
    if visit is not None:
        safe_delay(embed_patient_chunks, visit.patient_id)
        safe_delay(summarize_visit, visit.id)
    return {"deleted": True}


@router.patch("/visits/{visit_id}", response_model=VisitRead)
def update_visit(
    visit_id: str,
    data: VisitUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    patch = data.model_dump(exclude_unset=True)
    if "visit_date" in patch:
        try:
            patch["visit_date"] = (
                date.fromisoformat(patch["visit_date"]) if patch["visit_date"] else date.today()
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="visit_date must be YYYY-MM-DD")
    if "clinic_id" in patch:
        clinic_id = patch.pop("clinic_id")
        if clinic_id:
            clinic = db.get(Clinic, clinic_id)
            if clinic is None or not clinic.active:
                raise HTTPException(status_code=400, detail="Unknown clinic")
            visit.clinic_id = clinic.id
        else:
            visit.clinic_id = None
    for field, value in patch.items():
        setattr(visit, field, value)
    db.commit()
    db.refresh(visit)
    safe_delay(embed_patient_chunks, visit.patient_id)
    if "notes" in patch:
        safe_delay(summarize_visit, visit.id)
    visit.attachments = (
        db.scalars(select(Attachment).where(Attachment.visit_id == visit.id)).all()
    )
    _with_transcriptions(db, visit.attachments)
    visit.clinic = db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
    visit.sections = (
        db.scalars(
            select(VisitSection)
            .where(VisitSection.visit_id == visit.id)
            .order_by(VisitSection.created_at)
        ).all()
    )
    _set_creator_names(db, [visit])
    return visit


def _name_visit(db: Session, visit: Visit) -> None:
    names = _release_names(db, {visit.released_by} if visit.released_by else set())
    visit.released_by_name = names.get(visit.released_by or "")


@router.patch("/visits/{visit_id}/summary", response_model=VisitRead)
def update_visit_summary(
    visit_id: str,
    data: VisitSummaryUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clinician edit of the three patient-facing lines. Editing a
    released summary returns it to draft — unreviewed text never shows."""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    visit.patient_summary = {
        "en": data.en.strip(),
        "sw": data.sw.strip(),
        "lg": data.lg.strip(),
    }
    if (visit.summary_status or "draft") == "released":
        visit.summary_status = "draft"
        visit.released_by = None
        visit.released_at = None
    db.commit()
    db.refresh(visit)
    _populate_visit(db, visit)
    _name_visit(db, visit)
    _set_creator_names(db, [visit])
    return visit


@router.post("/visits/{visit_id}/release", response_model=VisitRead)
def release_visit_summary(
    visit_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Release a draft summary to the patient portal, recording who and when."""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    if not (visit.patient_summary or {}).get("en", "").strip():
        raise HTTPException(status_code=400, detail="No summary to release yet")
    visit.summary_status = "released"
    visit.released_by = current.id
    visit.released_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(visit)
    _populate_visit(db, visit)
    _name_visit(db, visit)
    _set_creator_names(db, [visit])
    return visit
