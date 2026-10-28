import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Specialty(Base):
    """Review specialty (HIV care, Cardiology, Pharmacy, ...).

    Reviews are routed to the members of the chosen specialties.
    """

    __tablename__ = "specialties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SpecialtyMember(Base):
    """Staff assigned to a specialty. A specialty holds any number of users
    (e.g. several pharmacists in Pharmacy)."""

    __tablename__ = "specialty_members"
    __table_args__ = (
        UniqueConstraint("specialty_id", "user_id", name="uq_specialty_member"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    specialty_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specialties.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
