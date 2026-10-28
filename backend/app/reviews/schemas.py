from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BriefItemSnapshot(BaseModel):
    specialty: str = ""
    concern: str = ""
    citation: str = ""
    certainty: str = "low"
    status: str = "suggested"


class BriefSnapshot(BaseModel):
    specialties: list[str] = []
    items: list[BriefItemSnapshot] = []
    interactions: list[str] = []
    overdue_checks: list[str] = []


class ReviewCreate(BaseModel):
    patient_id: str
    # Empty specialty_ids + explicit user_ids = hand-picked recipients only.
    specialty_ids: list[str] = []
    user_ids: list[str] = []
    message: str = ""
    brief: BriefSnapshot = BriefSnapshot()


class ReviewUpdate(BaseModel):
    status: str


class RecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    email: str = ""
    full_name: str | None = None
    specialty_id: str | None = None
    specialty_name: str | None = None
    emailed: bool = False


class ResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author_id: str
    author_email: str = ""
    author_name: str | None = None
    text: str
    has_audio: bool = False
    has_image: bool = False
    created_at: datetime


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    patient_name: str = ""
    requested_by: str
    requester_email: str = ""
    message: str = ""
    brief_snapshot: dict = {}
    status: str
    created_at: datetime
    closed_at: datetime | None = None
    recipients: list[RecipientRead] = []
    responses: list[ResponseRead] = []
    response_count: int = 0
