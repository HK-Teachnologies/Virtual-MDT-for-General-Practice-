from datetime import datetime

from pydantic import BaseModel, field_validator


class BriefRequest(BaseModel):
    patient_id: str


class BriefItemRead(BaseModel):
    id: str
    specialty: str
    concern: str
    citation: str
    certainty: str
    status: str
    edited_text: str | None = None
    source_type: str = ""
    question: str = ""
    urgent: bool = False
    selfcheck_reason: str = ""
    cited_labels: list[dict] = []


class BriefRunRead(BaseModel):
    id: str
    patient_id: str
    status: str
    current_step: str
    model: str
    prompt_version: str
    patient_summary: dict = {}
    specialties: list[str] = []

    @field_validator("patient_summary", mode="before")
    @classmethod
    def _null_summary_to_empty(cls, value: object) -> dict:
        """Pre-0018 runs store NULL: treat a missing summary as empty."""
        return value if isinstance(value, dict) else {}
    error: str = ""
    created_at: datetime
    completed_at: datetime | None = None
    items: list[BriefItemRead] = []
    interactions: list[dict] = []
    overdue_checks: list[dict] = []
    removed_points: list[dict] = []


class BriefItemUpdate(BaseModel):
    status: str
    edited_text: str | None = None


class GuidelineRead(BaseModel):
    id: str
    title: str
    version: str
    active: bool
    chunks: int
    index_status: str = "ready"
    index_error: str = ""


class GuidelineUpdate(BaseModel):
    active: bool


class TranscriptionRead(BaseModel):
    id: str
    attachment_id: str
    kind: str
    text: str
    verified: bool
    model: str


class TranscriptionUpdate(BaseModel):
    """Staff correction/verification of a machine read."""

    text: str | None = None
    verified: bool | None = None
