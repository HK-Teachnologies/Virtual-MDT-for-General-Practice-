from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.mdt.schemas import TranscriptionRead


def _coerce_summary(value: object) -> dict:
    """Pre-0019 rows store NULL: treat a missing summary as empty."""
    return value if isinstance(value, dict) else {}


class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    district: str | None = None
    address: str | None = None
    weight_kg: float | None = None
    height_cm: float | None = None


class PatientUpdate(BaseModel):
    """Staff edit of patient details and optional measurements. Only
    provided fields change; measurements must be positive when given."""

    full_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    district: str | None = None
    address: str | None = None
    weight_kg: float | None = None
    height_cm: float | None = None


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str | None = None
    created_by_name: str | None = None
    transcription: TranscriptionRead | None = None


class ClinicRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_date: date
    notes: str
    source: str
    patient_summary: dict = {}
    summary_status: str = "draft"
    released_by_name: str | None = None
    released_at: datetime | None = None
    clinic: ClinicRef | None = None
    created_by_name: str | None = None

    _null_summary_to_empty = field_validator("patient_summary", mode="before")(
        _coerce_summary
    )

    _null_status_to_draft = field_validator("summary_status", mode="before")(
        lambda v: v or "draft"
    )
    attachments: list[AttachmentRead] = []
    sections: list["SectionRead"] = []


class VisitSummaryUpdate(BaseModel):
    """Clinician edit of the three patient-facing lines. Editing a
    released summary returns it to draft."""

    en: str
    sw: str
    lg: str


class SectionCreate(BaseModel):
    section: str
    content: str


class SectionUpdate(BaseModel):
    section: str | None = None
    content: str | None = None


class SectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section: str
    content: str
    created_by_name: str | None = None
    created_at: datetime


class VisitUpdate(BaseModel):
    notes: str | None = None
    visit_date: str | None = None
    clinic_id: str | None = None
    source: str | None = None


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    district: str | None = None
    address: str | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    created_at: datetime
    visits: list[VisitRead] = []
    # The list endpoint omits full visits; this carries the count instead.
    visit_count: int = 0
    # Attention signals for triage: still-open specialist reviews and
    # machine reads waiting for staff verification.
    open_review_count: int = 0
    unverified_read_count: int = 0
