"""Background MDT pipeline (Celery): transcribe -> plan -> retrieve -> draft -> self-check.

One task per stage boundary that matters operationally; the brief itself runs
as a single task with per-step status updates so the frontend can poll honest
progress. In tests (CELERY_TASK_ALWAYS_EAGER=1) everything runs inline.
"""

import logging
from datetime import datetime
from pathlib import Path

from celery import Celery
from sqlalchemy import delete, select

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.db.session import SessionLocal
from app.llm import client as llm
from app.llm.prompts import DRAFT_SYSTEM, PLAN_SYSTEM, SELFCHECK_SYSTEM

# Register every table in metadata. The web app gets this via main.py, but
# the worker boots straight into this module — without these imports the
# users FKs cannot resolve and every task fails at flush.
from app.clinics import models as _clinic_models  # noqa: E402,F401
from app.patient_auth import models as _otp_models  # noqa: E402,F401
from app.patients import models as _patient_models  # noqa: E402,F401
from app.profiles import models as _profile_models  # noqa: E402,F401
from app.users import models as _user_models  # noqa: E402,F401
from app.mdt import retrieval
from app.mdt.models import (
    BriefItem,
    BriefRun,
    GuidelineChunk,
    GuidelineDoc,
    PatientChunk,
    Transcription,
)

celery_app = Celery("virtual_mdt", broker=settings.redis_url)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_store_eager_result=True,
)


def safe_delay(task, *args, **kwargs) -> None:
    """Enqueue without ever breaking the request when the queue is down."""
    try:
        task.delay(*args, **kwargs)
    except Exception:
        pass


def chunk_text(text: str, size: int = 800) -> list[str]:
    parts = [p.strip() for p in text.replace("\r", "").split("\n\n")]
    chunks, current = [], ""
    for part in parts:
        if len(current) + len(part) + 2 <= size:
            current = f"{current}\n\n{part}".strip()
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return [c for c in chunks if c]


def _timeline_text(db, patient_id: str) -> str:
    """De-identified case text: dates, clinics, notes, sections. No names,
    phones, or emails ever leave the database towards the model."""
    from app.clinics.models import Clinic
    from app.patients.models import Attachment, Patient, Visit, VisitSection

    patient = db.get(Patient, patient_id)
    visits = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date)
        ).all()
    )
    lines = [
        f"Patient: adult, sex {patient.sex or 'unknown'}, "
        f"DOB {patient.date_of_birth or 'unknown'}."
    ]
    for visit in visits:
        clinic = db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
        lines.append(
            f"\nVisit {visit.visit_date} [{clinic.name if clinic else 'general'}]: "
            f"{visit.notes or '(no notes)'}"
        )
        sections = db.scalars(
            select(VisitSection).where(VisitSection.visit_id == visit.id)
        ).all()
        for section in sections:
            lines.append(f"  {section.section}: {section.content}")
        attachments = db.scalars(
            select(Attachment).where(Attachment.visit_id == visit.id)
        ).all()
        for attachment in attachments:
            tr = db.scalar(
                select(Transcription).where(
                    Transcription.attachment_id == attachment.id
                )
            )
            if tr and tr.text:
                tag = "verified" if tr.verified else "UNVERIFIED machine read"
                lines.append(f"  attached {tr.kind} ({tag}): {tr.text}")
    return "\n".join(lines)


@celery_app.task(name="mdt.transcribe_attachment")
def transcribe_attachment(attachment_id: str) -> str:
    from app.patients.models import Attachment

    with SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        if attachment is None:
            return "missing"
        mime = attachment.content_type or ""
        filename_lower = attachment.filename.lower()
        # Browsers and curl don't always label audio correctly (curl sends
        # application/octet-stream unless told otherwise), so fall back to
        # the file extension for common voice-note formats.
        is_audio = mime.startswith("audio/") or (
            mime in ("", "application/octet-stream")
            and filename_lower.endswith(
                (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".wma")
            )
        )
        if is_audio:
            kind, text = "audio", llm.transcribe_audio(attachment.stored_path)
            model = settings.llm_transcribe_model
        elif filename_lower.endswith((".pdf", ".txt", ".md")):
            # Deterministic read (PyMuPDF/UTF-8) — no model call needed.
            # This is the patient-record path for uploaded documents.
            kind = "document"
            text = extract_document_text(
                attachment.filename, Path(attachment.stored_path).read_bytes()
            )
            model = "pymupdf" if filename_lower.endswith(".pdf") else "utf-8"
        else:
            kind = "image"
            text = llm.describe_image(
                attachment.stored_path,
                mime,
                "Transcribe everything readable in this photo (handwritten notes, "
                "lab slip, or patient-held book entry). Reply with the transcribed "
                "text only, preserving structure.",
            )
            model = settings.llm_vision_model or settings.llm_model
        existing = db.scalar(
            select(Transcription).where(
                Transcription.attachment_id == attachment.id
            )
        )
        if existing:
            existing.kind, existing.text, existing.model = kind, text, model
        else:
            db.add(
                Transcription(
                    attachment_id=attachment.id, kind=kind, text=text, model=model
                )
            )
        patient_id = _patient_of(db, attachment.visit_id)
        db.commit()
        safe_delay(embed_patient_chunks, patient_id)
        return "ok"


def _patient_of(db, visit_id: str) -> str:
    from app.patients.models import Visit

    visit = db.get(Visit, visit_id)
    return visit.patient_id if visit else ""


@celery_app.task(name="mdt.embed_patient_chunks")
def embed_patient_chunks(patient_id: str) -> str:
    if not patient_id:
        return "missing"
    from app.patients.models import Attachment, Visit, VisitSection

    with SessionLocal() as db:
        db.execute(delete(PatientChunk).where(PatientChunk.patient_id == patient_id))
        texts: list[tuple[str, str, str]] = []  # (source_type, source_id, text)
        visits = db.scalars(
            select(Visit).where(Visit.patient_id == patient_id)
        ).all()
        for visit in visits:
            if visit.notes:
                texts.append(("visit", visit.id, f"{visit.visit_date}: {visit.notes}"))
            for section in db.scalars(
                select(VisitSection).where(VisitSection.visit_id == visit.id)
            ).all():
                texts.append(
                    ("section", section.id, f"{visit.visit_date} [{section.section}]: {section.content}")
                )
            for attachment in db.scalars(
                select(Attachment).where(Attachment.visit_id == visit.id)
            ).all():
                tr = db.scalar(
                    select(Transcription).where(
                        Transcription.attachment_id == attachment.id
                    )
                )
                if tr and tr.text:
                    texts.append(("transcription", tr.id, tr.text))
        if texts:
            vectors = llm.embed([t[2] for t in texts])
            for (source_type, source_id, text), vector in zip(texts, vectors):
                db.add(
                    PatientChunk(
                        patient_id=patient_id,
                        source_type=source_type,
                        source_id=source_id,
                        text=text,
                        embedding=vector,
                    )
                )
        db.commit()
        return f"{len(texts)} chunks"


def extract_document_text(filename: str, raw: bytes) -> str:
    """Readable text from a .txt, .md, or text-based .pdf upload.

    Shared by guideline indexing and patient-record ingestion.
    Raises ValueError with a staff-facing message when there is nothing
    readable (e.g. scanned-image PDFs).
    """
    if filename.lower().endswith(".pdf"):
        import fitz

        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as exc:
            raise ValueError("Could not read the PDF file") from exc
        pages = []
        for number, page in enumerate(doc, start=1):
            try:
                text = page.get_text().strip()
            except Exception:
                text = ""
            if text:
                pages.append(f"[page {number}]\n{text}")
        if not pages:
            raise ValueError(
                "The PDF has no readable text (it may be scanned images). "
                "Photograph key pages via Capture instead — those are read with vision."
            )
        return "\n\n".join(pages)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text") from exc


@celery_app.task(name="mdt.index_guideline")
def index_guideline(doc_id: str) -> str:
    """Chunk + embed one uploaded guideline in batches. A 1000+ page PDF
    means thousands of chunks — batching keeps each embedding call small
    and lets the upload return immediately."""
    with SessionLocal() as db:
        doc = db.get(GuidelineDoc, doc_id)
        if doc is None or not doc.stored_path:
            return "missing"
        doc.index_status = "indexing"
        doc.index_error = ""
        # A retry must not duplicate chunks committed by the earlier attempt.
        db.execute(delete(GuidelineChunk).where(GuidelineChunk.doc_id == doc.id))
        db.commit()
        try:
            raw = Path(doc.stored_path).read_bytes()
            text = extract_document_text(Path(doc.stored_path).name, raw)
            if not text.strip():
                raise ValueError("File has no readable text")
            # Larger chunks than patient notes: guideline prose needs its
            # section context, and every chunk carries its source so brief
            # citations can name the document.
            bodies = [
                f"{doc.title} ({doc.version or 'undated'}):\n{chunk}"
                for chunk in chunk_text(text, size=2000)
            ]
            # Small CPU-friendly batches: one /embed call for a 1000+ page
            # document can otherwise outlast the model-server HTTP timeout
            # on a small box and fail the whole run.
            batch_size = max(1, min(settings.llm_embed_batch, 32))
            for start in range(0, len(bodies), batch_size):
                batch = bodies[start : start + batch_size]
                vectors = llm.embed(batch)
                for offset, (body, vector) in enumerate(zip(batch, vectors)):
                    db.add(
                        GuidelineChunk(
                            doc_id=doc.id,
                            chunk_index=start + offset,
                            text=body,
                            embedding=vector,
                        )
                    )
                db.commit()
            doc.index_status = "ready"
            doc.index_error = ""
            db.commit()
            return f"{len(bodies)} chunks"
        except Exception as exc:
            logger.exception("Guideline indexing failed for %s", doc_id)
            db.rollback()
            doc = db.get(GuidelineDoc, doc_id)
            if doc is not None:
                doc.index_status = "failed"
                doc.index_error = str(exc)[:1000]
                db.commit()
            return "failed"


def _set_step(db, run: BriefRun, status: str, step: str) -> None:
    run.status, run.current_step = status, step
    db.commit()


def _normalize_interaction(raw: object) -> dict:
    """Coerce one draft interaction to the object shape the UI renders."""
    if isinstance(raw, str):
        return {"drugs": [], "concern": raw, "citation": "", "source_type": ""}
    point = raw if isinstance(raw, dict) else {}
    drugs = point.get("drugs", [])
    return {
        "drugs": [str(d) for d in drugs] if isinstance(drugs, list) else [],
        "concern": str(point.get("concern", "")),
        "citation": str(point.get("citation", "")),
        "source_type": str(point.get("source_type", "")),
    }


def _normalize_overdue_check(raw: object) -> dict:
    """Coerce one draft overdue check to the object shape the UI renders."""
    if isinstance(raw, str):
        return {"check": raw, "last_done": "", "citation": "", "source_type": ""}
    point = raw if isinstance(raw, dict) else {}
    return {
        "check": str(point.get("check", "")),
        "last_done": str(point.get("last_done", "")),
        "citation": str(point.get("citation", "")),
        "source_type": str(point.get("source_type", "")),
    }


@celery_app.task(name="mdt.run_brief", bind=True)
def run_brief(self, run_id: str) -> str:
    with SessionLocal() as db:
        run = db.get(BriefRun, run_id)
        if run is None:
            return "missing"
        try:
            _set_step(db, run, "planning", "Planning the review")
            case_text = _timeline_text(db, run.patient_id)
            plan = llm.complete_json(
                system=PLAN_SYSTEM,
                user=f"Case summary:\n{case_text}",
                kind="plan",
            )
            run.specialties = [str(s) for s in plan.get("specialties", [])][:4]
            run.model = settings.llm_model
            run.prompt_version = settings.prompt_version
            db.commit()

            _set_step(db, run, "retrieving", "Retrieving history and guidelines")
            queries = [str(q) for q in plan.get("queries", [])][:4] or ["overall review"]
            query_vectors = llm.embed(queries)
            history, guides = [], []
            for vector in query_vectors:
                history += retrieval.retrieve_patient_history(
                    db, patient_id=run.patient_id, query_vector=vector, k=4
                )
                guides += retrieval.retrieve_guidelines(db, query_vector=vector, k=4)
            seen, history_unique, guides_unique = set(), [], []
            for chunk in history:
                if chunk.id not in seen:
                    seen.add(chunk.id)
                    history_unique.append(chunk)
            for chunk in guides:
                if chunk.id not in seen:
                    seen.add(chunk.id)
                    guides_unique.append(chunk)
            evidence = "\n".join(
                ["Relevant past history:"]
                + [f"- {c.text}" for c in history_unique[:8]]
                + ["Guideline excerpts:"]
                + [f"- {c.text}" for c in guides_unique[:8]]
            )

            _set_step(db, run, "drafting", "Drafting the brief")
            draft = llm.complete_json(
                system=DRAFT_SYSTEM,
                user=f"Case summary:\n{case_text}\n\n{evidence}",
                kind="draft",
            )

            _set_step(db, run, "checking", "Self-checking citations")
            items = draft.get("items", [])
            verdicts = []
            if settings.llm_provider != "echo" and items:
                check = llm.complete_json(
                    system=SELFCHECK_SYSTEM,
                    user=f"Items:\n{items}\n\nEvidence:\n{evidence}",
                    kind="selfcheck",
                )
                verdicts = check.get("verdicts", [])
            keep = {v.get("index") for v in verdicts if v.get("keep")} if verdicts else set(range(len(items)))
            for index, item in enumerate(items):
                if index not in keep:
                    continue
                db.add(
                    BriefItem(
                        run_id=run.id,
                        specialty=str(item.get("specialty", ""))[:255],
                        concern=str(item.get("concern", "")),
                        citation=str(item.get("citation", "")),
                        certainty=str(item.get("certainty", "low"))[:32],
                        status="suggested",
                    )
                )
            run.specialties = [str(s) for s in draft.get("specialties", run.specialties or [])][:4]
            interactions = draft.get("interactions", [])
            overdue_checks = draft.get("overdue_checks", [])
            run.interactions = [
                _normalize_interaction(p) for p in (interactions if isinstance(interactions, list) else [])
            ]
            run.overdue_checks = [
                _normalize_overdue_check(p) for p in (overdue_checks if isinstance(overdue_checks, list) else [])
            ]
            db.commit()

            _set_step(db, run, "ready", "Ready for clinician review")
            run.completed_at = datetime.utcnow()
            db.commit()
            return "ready"
        except Exception as exc:
            run.status, run.current_step = "failed", "Failed"
            run.error = str(exc)[:2000]
            db.commit()
            return "failed"
