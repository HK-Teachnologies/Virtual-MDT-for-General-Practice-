import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# A review is a clinician's request for specialist input on a brief.
# pending   -> sent, awaiting responses
# responded -> at least one specialist replied
# closed    -> requester (or admin) closed the loop
REVIEW_STATUSES = frozenset({"pending", "responded", "closed"})


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), index=True
    )
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    message: Mapped[str] = mapped_column(Text, default="")
    # Snapshot of the brief at send time (specialties/items/citations), so
    # the review stands even as the live brief keeps evolving.
    brief_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewRecipient(Base):
    """One specialist the review was sent to (via a specialty or picked)."""

    __tablename__ = "review_recipients"
    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_recipient"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    specialty_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("specialties.id"), nullable=True
    )
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReviewResponse(Base):
    """A specialist's reply: always text (transcribed when voice was used),
    with the original recording kept when one was uploaded."""

    __tablename__ = "review_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id"), index=True
    )
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
