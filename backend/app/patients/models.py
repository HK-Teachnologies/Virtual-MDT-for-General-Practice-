import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Standard clinical sections a visit record can carry.
SECTION_TYPES = frozenset(
    {
        "lab",
        "imaging",
        "vitals",
        "notes",
        "diagnosis",
        "prescription",
        "referral",
        "other",
    }
)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    district: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Optional measurements, editable later (collapsed in the UI by default).
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date, default=date.today)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="typed")
    clinic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clinics.id"), nullable=True
    )
    # Patient-safe summary of this visit ({en, sw, lg}), written at record
    # time so the portal never needs an MDT review to exist. Plain words,
    # no doses, never the raw notes. Draft until a clinician releases it.
    patient_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    # Release gate: the portal serves only released summaries.
    summary_status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft"
    )
    released_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VisitSection(Base):
    __tablename__ = "visit_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    visit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("visits.id"), index=True
    )
    section: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    visit_id: Mapped[str] = mapped_column(String(36), ForeignKey("visits.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
