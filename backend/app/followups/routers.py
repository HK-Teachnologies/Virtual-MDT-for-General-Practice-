"""Doctor -> patient follow-up Q&A.

Staff ask questions on a patient record; the patient answers (typed text
or voice note) in the portal. Voice answers are transcribed so they are
always readable, and kept listenable.
"""

import logging
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.followups.models import FollowUp, PatientQuestion
from app.followups.schemas import (
    AnswerTranslation,
    FollowUpAsk,
    FollowUpRead,
    PatientQuestionAnswer,
    PatientQuestionRead,
)
from app.mdt.tasks import safe_delay, translate_followup
from app.llm import client as llm
from app.patient_auth.routers import get_current_patient, send_answer_notification
from app.patients.models import Patient
from app.users.models import USER_ROLES, User
from app.users.routers import get_current_user

router = APIRouter()

logger = logging.getLogger(__name__)

# Ask-the-doctor answering: every clinical cadre may answer; only the
# non-clinical "normal_user" role is read-only. All staff may view the inbox.
ANSWER_ROLES = USER_ROLES - {"normal_user"}


def _read(followup: FollowUp, db: Session) -> FollowUpRead:
    asker = db.get(User, followup.asked_by)
    return FollowUpRead(
        id=followup.id,
        patient_id=followup.patient_id,
        asked_by=followup.asked_by,
        asker_name=asker.full_name or asker.email if asker else "",
        question=followup.question,
        question_i18n=dict(followup.question_i18n or {}),
        answer_text=followup.answer_text or "",
        answer_original=followup.answer_original or "",
        has_audio=bool(followup.answer_audio_path),
        status=followup.status,
        created_at=followup.created_at,
        answered_at=followup.answered_at,
    )


@router.post("", response_model=FollowUpRead, status_code=201)
def ask_question(
    data: FollowUpAsk,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff ask the patient a follow-up question."""
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    followup = FollowUp(
        patient_id=patient.id, asked_by=current.id, question=data.question.strip()
    )
    db.add(followup)
    db.commit()
    db.refresh(followup)
    # Translate the staff question for the portal in the background.
    safe_delay(translate_followup, followup.id)
    # The task commits in its own session: reload so the response
    # carries translations when tasks run inline (tests).
    db.expire(followup, ["question_i18n"])
    return _read(followup, db)


@router.get("/for-patient/{patient_id}", response_model=list[FollowUpRead])
def for_patient(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff thread for one patient record, newest last."""
    rows = (
        db.scalars(
            select(FollowUp)
            .where(FollowUp.patient_id == patient_id)
            .order_by(FollowUp.created_at)
        ).all()
    )
    return [_read(r, db) for r in rows]


@router.get("/mine", response_model=list[FollowUpRead])
def my_questions(
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient portal: my questions, open first."""
    rows = (
        db.scalars(
            select(FollowUp)
            .where(FollowUp.patient_id == current.id)
            .order_by(FollowUp.created_at)
        ).all()
    )
    rows = sorted(rows, key=lambda r: (r.status != "open", r.created_at))
    return [_read(r, db) for r in rows]


@router.post("/{followup_id}/answer", response_model=FollowUpRead)
def answer_question(
    followup_id: str,
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient answers by text, voice recording, or both. Voice is
    transcribed to English text; the audio itself is never kept or served."""
    followup = db.get(FollowUp, followup_id)
    if followup is None or followup.patient_id != current.id:
        raise HTTPException(status_code=404, detail="Question not found")
    body = text.strip()
    original = ""
    audio_received = False
    if audio is not None:
        raw = audio.file.read()
        if raw:
            audio_received = True
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(audio.filename or "voice").name)
            stored = f"{uuid.uuid4().hex}_{safe}"
            voice_dir = Path(settings.upload_dir) / "followup_audio"
            voice_dir.mkdir(parents=True, exist_ok=True)
            audio_path = str(voice_dir / stored)
            (voice_dir / stored).write_bytes(raw)
            if not body:
                try:
                    original, body = llm.transcribe_to_english(audio_path)
                    original, body = original.strip(), body.strip()
                except llm.LLMError as exc:
                    raise HTTPException(
                        status_code=502, detail=f"Voice transcription failed: {exc}"
                    )
            # Transcription-only: free the disk, keep both texts.
            Path(audio_path).unlink(missing_ok=True)
    if not body:
        raise HTTPException(
            status_code=400,
            detail=(
                "We could not hear anything in your recording — please "
                "try again or type your answer"
                if audio_received
                else "Type an answer or record a voice note"
            ),
        )
    followup.answer_text = body
    followup.answer_original = original
    followup.answer_audio_path = None
    followup.status = "answered"
    followup.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(followup)
    return _read(followup, db)


def _read_question(question: PatientQuestion, db: Session) -> PatientQuestionRead:
    answerer = db.get(User, question.answered_by) if question.answered_by else None
    return PatientQuestionRead(
        id=question.id,
        patient_id=question.patient_id,
        question=question.question,
        question_original=question.question_original or "",
        answer_text=question.answer_text or "",
        answer_i18n=dict(question.answer_i18n or {}),
        answerer_name=answerer.full_name or answerer.email if answerer else "",
        status=question.status,
        created_at=question.created_at,
        answered_at=question.answered_at,
    )


ANSWER_I18N_SYSTEM = """Translate the clinician's answer for a patient into
English, Kiswahili, and Luganda. Keep the medical meaning exactly; use short
plain words a patient understands. Do not add advice and do not change the
instructions. Return JSON: {"en": "...", "sw": "...", "lg": "..."}."""


class TranslateDraft(BaseModel):
    text: str


@router.post("/patient-questions/translate", response_model=AnswerTranslation)
def translate_answer_draft(
    data: TranslateDraft,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Machine-translate an answer draft to EN/SW/LG for the doctor to check
    and edit before sending — the same release pattern as summaries."""
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to translate")
    try:
        raw = llm.complete_json(
            system=ANSWER_I18N_SYSTEM,
            user=text,
            kind="answer_i18n",
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=f"Translation failed: {exc}")
    return AnswerTranslation(
        en=text,
        sw=str(raw.get("sw", "") or "").strip() or text,
        lg=str(raw.get("lg", "") or "").strip() or text,
    )


@router.post("/patient-questions", response_model=PatientQuestionRead, status_code=201)
def ask_doctor(
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient asks the doctor: typed text, voice note, or both. Voice
    (Luganda/Kiswahili/English) is transcribed first; the audio is deleted
    and staff read the English text with the original kept alongside."""
    body = text.strip()
    original = ""
    audio_received = False
    if audio is not None:
        raw = audio.file.read()
        if raw:
            audio_received = True
            suffix = Path(audio.filename or "voice").suffix or ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(raw)
                audio_path = tmp.name
            if not body:
                try:
                    original, body = llm.transcribe_to_english(audio_path)
                    original, body = original.strip(), body.strip()
                except llm.LLMError as exc:
                    raise HTTPException(
                        status_code=502, detail=f"Voice transcription failed: {exc}"
                    )
                finally:
                    Path(audio_path).unlink(missing_ok=True)
            else:
                Path(audio_path).unlink(missing_ok=True)
    if not body:
        raise HTTPException(
            status_code=400,
            detail=(
                "We could not hear anything in your recording — please "
                "try again or type your question"
                if audio_received
                else "Type a question or record a voice note"
            ),
        )
    question = PatientQuestion(
        patient_id=current.id, question=body, question_original=original
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _read_question(question, db)


@router.get("/patient-questions/mine", response_model=list[PatientQuestionRead])
def my_asked_questions(
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient portal: questions I asked the doctor, open first."""
    rows = (
        db.scalars(
            select(PatientQuestion)
            .where(PatientQuestion.patient_id == current.id)
            .order_by(PatientQuestion.created_at)
        ).all()
    )
    rows = sorted(rows, key=lambda r: (r.status != "open", r.created_at))
    return [_read_question(r, db) for r in rows]


@router.get(
    "/patient-questions/for-patient/{patient_id}",
    response_model=list[PatientQuestionRead],
)
def patient_questions_for_patient(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff inbox for one patient record: questions waiting for an answer."""
    rows = (
        db.scalars(
            select(PatientQuestion)
            .where(PatientQuestion.patient_id == patient_id)
            .order_by(PatientQuestion.created_at)
        ).all()
    )
    return [_read_question(r, db) for r in rows]


@router.post(
    "/patient-questions/{question_id}/answer", response_model=PatientQuestionRead
)
def answer_patient_question(
    question_id: str,
    data: PatientQuestionAnswer,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff answer a patient's question on their record. Any clinical
    cadre may answer; the non-clinical "normal_user" role is read-only."""
    if current.role not in ANSWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot answer patient questions",
        )
    question = db.get(PatientQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if not data.answer_text.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")
    question.answer_text = data.answer_text.strip()
    sw = data.answer_sw.strip() or question.answer_text
    lg = data.answer_lg.strip() or question.answer_text
    question.answer_i18n = {"en": question.answer_text, "sw": sw, "lg": lg}
    question.answered_by = current.id
    question.status = "answered"
    question.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(question)
    # Best-effort nudge: the answer itself stays inside the portal and the
    # send must never fail the saved answer.
    patient = db.get(Patient, question.patient_id)
    if patient is not None and patient.email:
        try:
            send_answer_notification(patient.email)
        except Exception as exc:
            logger.warning("Answer notification failed: %s", exc)
    return _read_question(question, db)
