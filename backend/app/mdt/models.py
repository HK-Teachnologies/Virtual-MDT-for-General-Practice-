import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Dimension of the model server's embedding model (bge-base-en-v1.5).
# Changing it requires a migration altering the vector columns.
EMBED_DIM = 768

try:
    # Real vector column on Postgres (the db image ships pgvector);
    # plain JSON list on SQLite so the test suite keeps working.
    from pgvector.sqlalchemy import Vector

    Embedding = Vector(EMBED_DIM).with_variant(JSON(), "sqlite")
except ImportError:  # pgvector not installed
    Embedding = JSON()  # type: ignore[assignment]


# Lifecycle of one background brief generation.
RUN_STATUSES = frozenset(
    {
        "queued",
        "planning",
        "retrieving",
        "drafting",
        "checking",
        "ready",
        "failed",
    }
)

# Mirrors the frontend ItemStatus so sign-off persists server-side.
# "removed" marks points the self-check dropped: kept as an audit trail,
# never shown as suggestions and never sign-offable.
ITEM_STATUSES = frozenset({"suggested", "approved", "rejected", "edited", "removed"})


class BriefRun(Base):
    __tablename__ = "brief_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="queued")
    current_step: Mapped[str] = mapped_column(String(255), default="Queued")
    model: Mapped[str] = mapped_column(String(255), default="")
    prompt_version: Mapped[str] = mapped_column(String(255), default="v1")
    specialties: Mapped[list] = mapped_column(JSON, default=list)
    # Safety panels of the brief: drug interactions and overdue routine
    # checks, as structured points (shapes in the draft prompt).
    interactions: Mapped[list] = mapped_column(JSON, default=list)
    overdue_checks: Mapped[list] = mapped_column(JSON, default=list)
    # Dropped safety-panel points: [{kind, point, reason}].
    removed_points: Mapped[list] = mapped_column(JSON, default=list)
    # Patient-safe summary of the visit ({en, sw, lg}), written for the
    # patient portal. Never the raw brief: plain words, no doses.
    patient_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BriefItem(Base):
    __tablename__ = "brief_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("brief_runs.id"), index=True
    )
    specialty: Mapped[str] = mapped_column(String(255), default="")
    concern: Mapped[str] = mapped_column(Text, default="")
    citation: Mapped[str] = mapped_column(Text, default="")
    certainty: Mapped[str] = mapped_column(String(32), default="low")
    status: Mapped[str] = mapped_column(String(32), default="suggested")
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # New draft shape (prompt v2): evidence source, question for the
    # doctor, urgency flag, and why the self-check removed this point.
    # `certainty` is legacy: kept for old rows, no longer written.
    source_type: Mapped[str] = mapped_column(String(32), default="")
    question: Mapped[str] = mapped_column(Text, default="")
    urgent: Mapped[bool] = mapped_column(default=False)
    selfcheck_reason: Mapped[str] = mapped_column(Text, default="")
    # Guideline tags this point cited, validated against the retrieved
    # evidence: [{label, doc_id, page}]. Shown (and linked) in the UI.
    cited_labels: Mapped[list] = mapped_column(JSON, default=list)


class Transcription(Base):
    """Machine read of one attachment (photo via vision, audio via STT).

    Always shown to staff as AI-suggested text to verify — never silently
    merged into the record.
    """

    __tablename__ = "transcriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    attachment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attachments.id"), unique=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # image | audio
    text: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(default=False)
    model: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GuidelineDoc(Base):
    """Admin-uploaded clinical knowledge source (e.g. Uganda Clinical Guidelines)."""

    __tablename__ = "guideline_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64), default="")
    active: Mapped[bool] = mapped_column(default=True)
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # A 1000+ page guideline takes minutes to embed, so indexing runs in the
    # worker. Retrieval only uses docs that are fully indexed (ready).
    index_status: Mapped[str] = mapped_column(String(32), default="indexing")
    index_error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GuidelineChunk(Base):
    __tablename__ = "guideline_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("guideline_docs.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(default=0)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Embedding)
    # 1-based source pages this chunk was cut from, so brief citations
    # can name (and link to) the exact page. Null for legacy chunks.
    page_start: Mapped[int | None] = mapped_column(nullable=True)
    page_end: Mapped[int | None] = mapped_column(nullable=True)


class PatientChunk(Base):
    """Embedded slice of one patient's record. Always scoped by patient_id —
    retrieval never crosses patients."""

    __tablename__ = "patient_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32))  # visit | section | transcription
    source_id: Mapped[str] = mapped_column(String(36))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Embedding)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
