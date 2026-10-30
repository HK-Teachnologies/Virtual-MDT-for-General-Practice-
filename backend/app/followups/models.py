"""Doctor -> patient follow-up questions (answered in the patient portal)
and patient -> doctor questions (asked in the portal, answered by staff)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), index=True
    )
    asked_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text, default="")
    # Original-language transcript of a voice answer, kept so bilingual
    # staff can check the English translation. Empty for typed answers.
    answer_original: Mapped[str] = mapped_column(Text, default="")
    # Staff question translated at ask time ({en, sw, lg}) so patients
    # read follow-ups in their language. Empty until the worker fills it.
    question_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    answer_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PatientQuestion(Base):
    """Patient -> doctor questions: asked in the portal by text or voice
    note, answered by staff on the patient record."""

    __tablename__ = "patient_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), index=True
    )
    # English text staff read. Voice questions are transcribed first.
    question: Mapped[str] = mapped_column(Text, default="")
    # Original-language transcript of a voice question, kept so bilingual
    # staff can check the English. Empty for typed questions.
    question_original: Mapped[str] = mapped_column(Text, default="")
    answer_text: Mapped[str] = mapped_column(Text, default="")
    # Clinician-checked translations of the answer ({en, sw, lg}), edited
    # before sending the same way summaries are released.
    answer_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    answered_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
