"""Background MDT pipeline (Celery): transcribe -> plan -> retrieve -> draft -> self-check.

One task per stage boundary that matters operationally; the brief itself runs
as a single task with per-step status updates so the frontend can poll honest
progress. In tests (CELERY_TASK_ALWAYS_EAGER=1) everything runs inline.
"""

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from celery import Celery
from sqlalchemy import delete, select

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.db.session import SessionLocal
from app.llm import client as llm
from app.llm.prompts import (
    DRAFT_SYSTEM,
    FOLLOWUP_QUESTION_SYSTEM,
    PATIENT_SUMMARY_SYSTEM,
    PLAN_SYSTEM,
    SELFCHECK_SYSTEM,
    VISIT_SUMMARY_SYSTEM,
)

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
    # Never let Celery reconfigure logging: its dictConfig disables every
    # existing logger (disable_existing_loggers=True), which silently
    # blackholes backend log lines such as the dev-mode OTP log.
    worker_hijack_root_logger=False,
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
    """De-identified case text: age, sex, dates, clinics, notes, sections.

    No names, dates of birth, phones, or emails ever leave the database
    towards the model: the header carries age (not DOB), and every
    staff-typed or machine-read line is passed through redact_pii with
    the patient's own identifiers.
    """
    from app.clinics.models import Clinic
    from app.patients.models import Attachment, Patient, Visit, VisitSection

    patient = db.get(Patient, patient_id)
    identifiers = _patient_identifiers(patient)
    visits = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date)
        ).all()
    )
    lines = [
        f"Patient: {_age_years(patient.date_of_birth)}, sex {patient.sex or 'unknown'}."
    ]
    for visit in visits:
        clinic = db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
        lines.append(
            f"\nVisit {visit.visit_date} [{clinic.name if clinic else 'general'}]: "
            f"{redact_pii(visit.notes or '(no notes)', identifiers)}"
        )
        sections = db.scalars(
            select(VisitSection).where(VisitSection.visit_id == visit.id)
        ).all()
        for section in sections:
            lines.append(
                f"  {section.section}: {redact_pii(section.content, identifiers)}"
            )
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
                lines.append(
                    f"  attached {tr.kind} ({tag}): {redact_pii(tr.text, identifiers)}"
                )
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
            kind, text = "audio", llm.transcribe_to_english(attachment.stored_path)
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
        if is_audio:
            # Transcription-only: the text is the record; the bytes are
            # never served, so free the disk (kept on failure for retry).
            Path(attachment.stored_path).unlink(missing_ok=True)
        safe_delay(embed_patient_chunks, patient_id)
        # A machine read adds visit content: refresh the patient summary.
        safe_delay(summarize_visit, attachment.visit_id)
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


@celery_app.task(name="mdt.summarize_visit")
def summarize_visit(visit_id: str) -> str:
    """Patient-safe summary of one visit ({en, sw, lg}), written at record
    time so the portal never needs an MDT review to exist.

    Idempotent overwrite: re-runs whenever visit content lands (new visit,
    edited notes, sections, transcriptions). Every write resets to draft
    and clears any release — only a clinician release shows it to the
    patient. Failures only log.
    """
    from app.clinics.models import Clinic
    from app.patients.models import Attachment, Patient, Visit, VisitSection

    with SessionLocal() as db:
        visit = db.get(Visit, visit_id)
        if visit is None:
            return "missing"
        patient = db.get(Patient, visit.patient_id)
        identifiers = _patient_identifiers(patient)
        clinic = db.get(Clinic, visit.clinic_id) if visit.clinic_id else None
        parts = [
            f"Visit {visit.visit_date} [{clinic.name if clinic else 'general'}]: "
            f"{redact_pii((visit.notes or '(no notes)')[:1000], identifiers)}"
        ]
        for section in db.scalars(
            select(VisitSection).where(VisitSection.visit_id == visit.id)
        ).all():
            parts.append(
                f"{section.section}: {redact_pii((section.content or '')[:500], identifiers)}"
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
                parts.append(
                    f"attached {tr.kind}: {redact_pii(tr.text[:500], identifiers)}"
                )
        if settings.llm_provider == "echo":
            summary = {
                "en": "Echo visit summary.",
                "sw": "Muhtasari wa echo wa ziara.",
                "lg": "Echo okusumulula kwa IPS.",
            }
        else:
            try:
                raw = llm.complete_json(
                    system=VISIT_SUMMARY_SYSTEM,
                    user="\n".join(parts),
                    kind="visit_summary",
                )
            except Exception as exc:
                logger.warning("Visit summary failed, continuing: %s", exc)
                return "failed"
            summary = {
                lang: str(raw.get(lang, ""))
                for lang in ("en", "sw", "lg")
            }
        visit.patient_summary = summary
        visit.summary_status = "draft"
        visit.released_by = None
        visit.released_at = None
        db.commit()
        return "ok"


@celery_app.task(name="mdt.translate_followup")
def translate_followup(followup_id: str) -> str:
    """Translate a staff follow-up question to EN/SW/LG for the portal.

    The question itself is clinician-written; only the mechanical
    translation is machine-made. Failures only log — the portal falls
    back to the original wording.
    """
    from app.followups.models import FollowUp
    from app.patients.models import Patient

    with SessionLocal() as db:
        followup = db.get(FollowUp, followup_id)
        if followup is None:
            return "missing"
        patient = db.get(Patient, followup.patient_id)
        text = redact_pii(followup.question, _patient_identifiers(patient))
        if settings.llm_provider == "echo":
            i18n = {
                "en": followup.question,
                "sw": "Swali la echo.",
                "lg": "Ekibuuzo kya echo.",
            }
        else:
            try:
                raw = llm.complete_json(
                    system=FOLLOWUP_QUESTION_SYSTEM,
                    user=text,
                    kind="question_i18n",
                )
            except Exception as exc:
                logger.warning("Follow-up translation failed, continuing: %s", exc)
                return "failed"
            i18n = {
                lang: str(raw.get(lang, ""))
                for lang in ("en", "sw", "lg")
            }
        followup.question_i18n = i18n
        db.commit()
        return "ok"


@celery_app.task(name="mdt.prepare_patient_summary")
def prepare_patient_summary(run_id: str) -> str:
    """Overall patient message for one brief run, from signed-off items only.

    Only items the doctor approved — or edited (using the edited wording) —
    reach the prompt. Suggested, rejected and removed points, interactions
    and overdue checks are never included. The result starts as draft; a
    clinician release shows it to the patient.
    """
    from app.patients.models import Patient

    with SessionLocal() as db:
        run = db.get(BriefRun, run_id)
        if run is None:
            return "missing"
        patient = db.get(Patient, run.patient_id)
        identifiers = _patient_identifiers(patient)
        items = (
            db.scalars(select(BriefItem).where(BriefItem.run_id == run.id)).all()
        )
        signed_off = []
        for item in items:
            if item.status == "approved":
                text = item.concern
                if item.question:
                    text += f" Question for the doctor: {item.question}"
                signed_off.append(
                    {"specialty": item.specialty, "point": text}
                )
            elif item.status == "edited":
                signed_off.append(
                    {
                        "specialty": item.specialty,
                        "point": item.edited_text or item.concern,
                    }
                )
        if not signed_off:
            logger.warning("No signed-off items for run %s, skipping summary", run_id)
            return "empty"
        payload = [
            {
                "specialty": entry["specialty"],
                "point": redact_pii(entry["point"], identifiers),
            }
            for entry in signed_off
        ]
        if settings.llm_provider == "echo":
            summary = {
                "en": "Echo patient summary.",
                "sw": "Muhtasari wa mgonjwa wa echo.",
                "lg": "Echo okusumulula kwomulwadde.",
            }
        else:
            try:
                raw = llm.complete_json(
                    system=PATIENT_SUMMARY_SYSTEM,
                    user=json.dumps({"approved_points": payload}, indent=2),
                    kind="summary",
                )
            except Exception as exc:
                logger.warning("Patient summary failed, continuing: %s", exc)
                return "failed"
            summary = {
                lang: str(raw.get(lang, ""))
                for lang in ("en", "sw", "lg")
            }
        run.patient_summary = summary
        run.summary_status = "draft"
        run.released_by = None
        run.released_at = None
        db.commit()
        return "ok"


def extract_document_pages(filename: str, raw: bytes) -> list[tuple[int, str]]:
    """Readable text per source page: [(1-based page number, text)].

    Blank pages are skipped but numbering follows the original document,
    so chunk page ranges always match the file staff can download.
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
                pages.append((number, text))
        if not pages:
            raise ValueError(
                "The PDF has no readable text (it may be scanned images). "
                "Photograph key pages via Capture instead — those are read with vision."
            )
        return pages
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text") from exc
    return [(1, text)]


def extract_document_text(filename: str, raw: bytes) -> str:
    """Readable text from a .txt, .md, or text-based .pdf upload.

    Shared by guideline indexing and patient-record ingestion.
    Raises ValueError with a staff-facing message when there is nothing
    readable (e.g. scanned-image PDFs).
    """
    pages = extract_document_pages(filename, raw)
    if filename.lower().endswith(".pdf"):
        return "\n\n".join(f"[page {number}]\n{text}" for number, text in pages)
    return pages[0][1]


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
            pages = extract_document_pages(Path(doc.stored_path).name, raw)
            if not "".join(text for _, text in pages).strip():
                raise ValueError("File has no readable text")
            # Larger chunks than patient notes: guideline prose needs its
            # section context, and every chunk carries its source so brief
            # citations can name the document. Chunking stays inside one
            # source page, so each chunk knows its page range for citations.
            prefix = f"{doc.title} ({doc.version or 'undated'}):\n"
            bodies: list[tuple[str, int, int]] = []  # (text, page_start, page_end)
            for number, text in pages:
                for chunk in chunk_text(text, size=2000):
                    bodies.append((f"{prefix}{chunk}", number, number))
            if not bodies:
                raise ValueError("File has no readable text")
            # Small CPU-friendly batches: one /embed call for a 1000+ page
            # document can otherwise outlast the model-server HTTP timeout
            # on a small box and fail the whole run.
            batch_size = max(1, min(settings.llm_embed_batch, 32))
            for start in range(0, len(bodies), batch_size):
                batch = bodies[start : start + batch_size]
                vectors = llm.embed([body for body, _, _ in batch])
                for offset, ((body, page_start, page_end), vector) in enumerate(
                    zip(batch, vectors)
                ):
                    db.add(
                        GuidelineChunk(
                            doc_id=doc.id,
                            chunk_index=start + offset,
                            text=body,
                            embedding=vector,
                            page_start=page_start,
                            page_end=page_end,
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


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _redact_phones(text: str) -> str:
    """Replace phone-like digit runs (9-15 digits, optional +, spaces,
    dashes, brackets) with [phone redacted]. Runs containing '/' or '.'
    are left alone so BP readings, dates and decimals survive."""

    def _sub(match: re.Match) -> str:
        raw = match.group(0)
        if "/" in raw or "." in raw:
            return raw
        digits = re.sub(r"\D", "", raw)
        if 9 <= len(digits) <= 15:
            return "[phone redacted]"
        return raw

    return re.sub(r"\+?[\d][\d\s\-()]{7,}[\d]", _sub, text)


def redact_pii(text: str, identifiers: list[tuple[str, str]]) -> str:
    """Strip direct identifiers before text leaves the database towards a
    model.

    identifiers is [(value, label)] — e.g. the patient's own name, phone
    and email, matched exactly (case-insensitive). Name tokens of 4+
    letters are also matched, except everyday words ("patient", "mother",
    ...). Any other email or phone-like number is caught by pattern.
    Clinical numbers (dates, BP, lab values) are preserved.
    """
    clean = text or ""
    for value, label in identifiers:
        if value and value.strip():
            clean = re.sub(
                re.escape(value.strip()), label, clean, flags=re.IGNORECASE
            )
    tokens = set()
    for value, label in identifiers:
        if label != "[name redacted]":
            continue
        for token in re.split(r"\s+", value or ""):
            token = re.sub(r"[^A-Za-z]", "", token)
            if len(token) >= 4 and token.lower() not in _NAME_TOKEN_STOPLIST:
                tokens.add(token)
    for token in sorted(tokens, key=len, reverse=True):
        clean = re.sub(
            rf"\b{re.escape(token)}\b", "[name redacted]", clean, flags=re.IGNORECASE
        )
    clean = EMAIL_RE.sub("[email redacted]", clean)
    return _redact_phones(clean)


_NAME_TOKEN_STOPLIST = frozenset(
    {
        "patient", "demo", "test", "user", "mother", "father", "baby", "child",
        "sister", "brother", "husband", "wife", "son", "daughter", "mister",
        "miss", "missus", "doctor", "nurse", "clinic",
    }
)


def _patient_identifiers(patient) -> list[tuple[str, str]]:
    return [
        (patient.full_name, "[name redacted]"),
        (patient.phone or "", "[phone redacted]"),
        (patient.email or "", "[email redacted]"),
    ]


def _age_years(born: date | None) -> str:
    if born is None:
        return "adult"
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return f"{age}-year-old"


# Used when the clinic has no specialties configured yet, so the planner
# still chooses from real review-routing names.
DEFAULT_SPECIALTIES = [
    "HIV care",
    "TB",
    "Cardiology",
    "Endocrinology",
    "Pharmacy",
    "Mental health",
    "Nutrition",
    "Maternal health",
]


def _canonical_specialties(names: object, allowed: list[str]) -> list[str]:
    """Keep only names on the clinic's specialty list (case-insensitive),
    stored with the list's canonical spelling, order preserved."""
    by_name = {name.strip().lower(): name for name in allowed if name.strip()}
    kept = []
    raw = names if isinstance(names, list) else []
    for name in raw:
        canon = by_name.get(str(name).strip().lower())
        if canon is not None and canon not in kept:
            kept.append(canon)
    return kept


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


GUIDE_TAG_RE = re.compile(r"\[G(\d+)\]")


def _validate_guideline_citation(citation: str, guide_tags: dict) -> list[dict]:
    """Cited labels for the [Gn] tags in a point that exist in this run's
    retrieved evidence. Empty when the point cites no retrieved excerpt —
    the caller drops such guideline-sourced points."""
    found = []
    for number in GUIDE_TAG_RE.findall(citation or ""):
        tag = f"G{number}"
        entry = guide_tags.get(tag)
        if entry is not None and entry not in found:
            found.append(entry)
    return found


def _normalize_item(raw: object) -> dict:
    """Coerce one draft item to the object shape the UI renders."""
    point = raw if isinstance(raw, dict) else {}
    urgent = point.get("urgent", False)
    if isinstance(urgent, str):
        urgent = urgent.strip().lower() in ("true", "yes", "1")
    return {
        "specialty": str(point.get("specialty", "")),
        "concern": str(point.get("concern", "")),
        "question": str(point.get("question", "")),
        "citation": str(point.get("citation", "")),
        "source_type": str(point.get("source_type", "")),
        "urgent": bool(urgent),
    }


@celery_app.task(name="mdt.run_brief", bind=True)
def run_brief(self, run_id: str) -> str:
    with SessionLocal() as db:
        run = db.get(BriefRun, run_id)
        if run is None:
            return "missing"
        try:
            _set_step(db, run, "planning", "Planning the review")
            from app.specialties.models import Specialty

            specialty_rows = (
                db.scalars(
                    select(Specialty)
                    .where(Specialty.active.is_(True))
                    .order_by(Specialty.name)
                ).all()
            )
            allowed_specialties = [s.name for s in specialty_rows if (s.name or "").strip()]
            if not allowed_specialties:
                allowed_specialties = list(DEFAULT_SPECIALTIES)
            case_text = _timeline_text(db, run.patient_id)
            plan = llm.complete_json(
                system=PLAN_SYSTEM.format(
                    specialty_list=", ".join(allowed_specialties)
                ),
                user=f"Case summary:\n{case_text}",
                kind="plan",
            )
            run.specialties = _canonical_specialties(
                plan.get("specialties", []), allowed_specialties
            )[:4]
            run.model = settings.llm_model
            run.prompt_version = settings.prompt_version
            db.commit()

            _set_step(db, run, "retrieving", "Retrieving history and guidelines")
            queries = [str(q) for q in plan.get("queries", [])][:6] or ["overall review"]
            query_vectors = llm.embed(queries)
            history, guides = [], []
            for query, vector in zip(queries, query_vectors):
                history += retrieval.retrieve_patient_history(
                    db, patient_id=run.patient_id, query_vector=vector, k=4
                )
                # Wide vector net, then the cross-encoder keeps the 4
                # excerpts that actually answer this query.
                candidates = retrieval.retrieve_guidelines(
                    db, query_vector=vector, k=20
                )
                order = llm.rerank(query, [c.text for c in candidates])
                guides += [
                    candidates[i] for i in order[:4] if i < len(candidates)
                ]
            seen, history_unique, guides_unique = set(), [], []
            for chunk in history:
                if chunk.id not in seen:
                    seen.add(chunk.id)
                    history_unique.append(chunk)
            for chunk in guides:
                if chunk.id not in seen:
                    seen.add(chunk.id)
                    guides_unique.append(chunk)
            # Guideline excerpts carry stable tags ([G1], [G2]...) with the
            # document name and page, so the model can cite them exactly
            # and the code can verify every citation afterwards.
            guide_tags: dict[str, dict] = {}
            guide_lines = []
            for number, chunk in enumerate(guides_unique[:8], start=1):
                tag = f"G{number}"
                doc = db.get(GuidelineDoc, chunk.doc_id)
                name = doc.title if doc else "Guideline"
                if doc and doc.version and doc.version not in doc.title:
                    name = f"{doc.title} ({doc.version})"
                pages = ""
                if chunk.page_start:
                    pages = f", p. {chunk.page_start}"
                    if chunk.page_end and chunk.page_end != chunk.page_start:
                        pages += f"\u2013{chunk.page_end}"
                label = f"{name}{pages}"
                guide_tags[tag] = {
                    "label": label,
                    "doc_id": chunk.doc_id,
                    "page": chunk.page_start,
                }
                guide_lines.append(f"[{tag}] {label}:\n{chunk.text}")
            logger.info(
                "Brief %s guideline evidence: %s",
                run.id,
                ", ".join(f"[{t}] {g['label']}" for t, g in guide_tags.items())
                or "none",
            )
            from app.patients.models import Patient as _Patient

            _patient = db.get(_Patient, run.patient_id)
            _identifiers = _patient_identifiers(_patient) if _patient else []
            evidence = "\n".join(
                ["Relevant past history:"]
                + [f"- {redact_pii(c.text, _identifiers)}" for c in history_unique[:8]]
                + ["Guideline excerpts:"]
                + guide_lines
            )

            _set_step(db, run, "drafting", "Drafting the brief")
            draft = llm.complete_json(
                system=DRAFT_SYSTEM,
                user=f"Case summary:\n{case_text}\n\n{evidence}",
                kind="draft",
            )

            _set_step(db, run, "checking", "Self-checking citations")
            raw_items = draft.get("items", [])
            raw_interactions = draft.get("interactions", [])
            raw_checks = draft.get("overdue_checks", [])
            points: list[dict] = []
            for index, raw in enumerate(raw_items if isinstance(raw_items, list) else []):
                points.append(
                    {"id": f"item-{index}", "kind": "item", "point": _normalize_item(raw)}
                )
            for index, raw in enumerate(
                raw_interactions if isinstance(raw_interactions, list) else []
            ):
                points.append(
                    {
                        "id": f"int-{index}",
                        "kind": "interaction",
                        "point": _normalize_interaction(raw),
                    }
                )
            for index, raw in enumerate(raw_checks if isinstance(raw_checks, list) else []):
                points.append(
                    {
                        "id": f"due-{index}",
                        "kind": "overdue_check",
                        "point": _normalize_overdue_check(raw),
                    }
                )
            check_user = json.dumps(
                {"points": points, "evidence": evidence}, indent=2
            )
            if settings.llm_provider == "echo":
                # Ids only exist at run time, so echo keeps every point here
                # in code instead of using a fixed canned fixture.
                verdicts = [
                    {"id": p["id"], "keep": True, "reason": "echo"} for p in points
                ]
            else:
                try:
                    check = llm.complete_json(
                        system=SELFCHECK_SYSTEM,
                        user=check_user,
                        kind="selfcheck",
                    )
                except Exception as exc:
                    run.status, run.current_step = "failed", "Failed"
                    run.error = f"Self-check failed: {exc}"[:2000]
                    db.commit()
                    return "failed"
                raw_verdicts = check.get("verdicts", [])
                verdicts = raw_verdicts if isinstance(raw_verdicts, list) else []
            by_id = {
                str(v.get("id")): v for v in verdicts if isinstance(v, dict)
            }
            kept_interactions, kept_checks, removed_points = [], [], []
            saved_items = []
            for entry in points:
                verdict = by_id.get(entry["id"])
                reason = (
                    str(verdict.get("reason") or "no verdict returned")
                    if isinstance(verdict, dict)
                    else "no verdict returned"
                )
                kept = isinstance(verdict, dict) and bool(verdict.get("keep"))
                # A guideline-sourced point must cite a [Gn] tag from this
                # run's evidence — otherwise the model invented the source.
                cited: list[dict] = []
                if entry["point"].get("source_type") == "guideline":
                    cited = _validate_guideline_citation(
                        entry["point"].get("citation", ""), guide_tags
                    )
                    if kept and not cited:
                        kept = False
                        reason = "cited guideline not in retrieved evidence"
                entry["cited"] = cited
                if not kept:
                    if entry["kind"] == "item":
                        db.add(
                            BriefItem(
                                run_id=run.id,
                                specialty=entry["point"]["specialty"][:255],
                                concern=entry["point"]["concern"],
                                citation=entry["point"]["citation"],
                                certainty="",
                                status="removed",
                                source_type=entry["point"]["source_type"][:32],
                                question=entry["point"]["question"],
                                urgent=entry["point"]["urgent"],
                                selfcheck_reason=reason,
                            )
                        )
                    else:
                        removed_points.append(
                            {
                                "kind": entry["kind"],
                                "point": entry["point"],
                                "reason": reason,
                            }
                        )
                    continue
                if entry["kind"] == "item":
                    db.add(
                        BriefItem(
                            run_id=run.id,
                            specialty=entry["point"]["specialty"][:255],
                            concern=entry["point"]["concern"],
                            citation=entry["point"]["citation"],
                            certainty="",
                            status="suggested",
                            source_type=entry["point"]["source_type"][:32],
                            question=entry["point"]["question"],
                            urgent=entry["point"]["urgent"],
                            cited_labels=entry["cited"],
                        )
                    )
                    saved_items.append(entry)
                elif entry["kind"] == "interaction":
                    entry["point"]["cited_labels"] = entry["cited"]
                    kept_interactions.append(entry["point"])
                else:
                    entry["point"]["cited_labels"] = entry["cited"]
                    kept_checks.append(entry["point"])
            draft_specialties = _canonical_specialties(
                draft.get("specialties", []), allowed_specialties
            )
            run.specialties = (draft_specialties or list(run.specialties or []))[:4]
            run.interactions = kept_interactions
            run.overdue_checks = kept_checks
            run.removed_points = removed_points
            db.commit()

            # The patient summary is NOT written here: it is prepared on
            # demand after sign-off (mdt.prepare_patient_summary), only from
            # approved/edited items, and released by a clinician.
            _set_step(db, run, "ready", "Ready for clinician review")
            run.completed_at = datetime.utcnow()
            db.commit()
            return "ready"
        except Exception as exc:
            run.status, run.current_step = "failed", "Failed"
            run.error = str(exc)[:2000]
            db.commit()
            return "failed"
