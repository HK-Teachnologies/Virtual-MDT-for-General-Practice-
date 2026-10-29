"""Doctor -> patient follow-up Q&A.

Staff ask questions on a patient record; the patient answers (typed text
or voice note) in the portal. Voice answers are transcribed so they are
always readable, and kept listenable.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.followups.models import FollowUp
from app.followups.schemas import FollowUpAsk, FollowUpRead
from app.mdt.tasks import safe_delay, translate_followup
from app.llm import client as llm
from app.patient_auth.routers import get_current_patient
from app.patients.models import Patient
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


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
    """Patient answers by text, voice recording, or both."""
    followup = db.get(FollowUp, followup_id)
    if followup is None or followup.patient_id != current.id:
        raise HTTPException(status_code=404, detail="Question not found")
    body = text.strip()
    audio_path: str | None = followup.answer_audio_path
    if audio is not None:
        raw = audio.file.read()
        if raw:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(audio.filename or "voice").name)
            stored = f"{uuid.uuid4().hex}_{safe}"
            voice_dir = Path(settings.upload_dir) / "followup_audio"
            voice_dir.mkdir(parents=True, exist_ok=True)
            (voice_dir / stored).write_bytes(raw)
            audio_path = str(voice_dir / stored)
            if not body:
                try:
                    body = llm.transcribe_audio(audio_path).strip()
                except llm.LLMError as exc:
                    raise HTTPException(
                        status_code=502, detail=f"Voice transcription failed: {exc}"
                    )
    if not body and audio_path is None:
        raise HTTPException(
            status_code=400, detail="Type an answer or record a voice note"
        )
    followup.answer_text = body
    followup.answer_audio_path = audio_path
    followup.status = "answered"
    followup.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(followup)
    return _read(followup, db)


@router.get("/{followup_id}/audio")
def followup_audio(
    followup_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff listen to a patient's voice answer."""
    followup = db.get(FollowUp, followup_id)
    if followup is None or not followup.answer_audio_path:
        raise HTTPException(status_code=404, detail="No recording for this answer")
    return FileResponse(followup.answer_audio_path, media_type="audio/webm")


@router.get("/mine/{followup_id}/audio")
def my_answer_audio(
    followup_id: str,
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient listens back to their own voice answer."""
    followup = db.get(FollowUp, followup_id)
    if (
        followup is None
        or followup.patient_id != current.id
        or not followup.answer_audio_path
    ):
        raise HTTPException(status_code=404, detail="No recording for this answer")
    return FileResponse(followup.answer_audio_path, media_type="audio/webm")
