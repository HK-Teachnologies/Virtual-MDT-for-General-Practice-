from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.mdt.schemas import TranscriptionRead


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
    clinic: ClinicRef | None = None
    attachments: list[AttachmentRead] = []
    sections: list["SectionRead"] = []


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
