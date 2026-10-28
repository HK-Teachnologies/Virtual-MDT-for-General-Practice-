"""Vector retrieval over patient history and guideline knowledge.

Patient history is always scoped to one patient_id — retrieval can never
leak another patient's record. On Postgres the ordering happens inside
pgvector; on SQLite (tests) it falls back to pure-Python cosine.
"""

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mdt.models import GuidelineChunk, GuidelineDoc, PatientChunk


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


def _is_postgres(db: Session) -> bool:
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def retrieve_patient_history(
    db: Session, *, patient_id: str, query_vector: list[float], k: int = 8
) -> list[PatientChunk]:
    if _is_postgres(db):
        return list(
            db.scalars(
                select(PatientChunk)
                .where(PatientChunk.patient_id == patient_id)
                .order_by(PatientChunk.embedding.cosine_distance(query_vector))
                .limit(k)
            ).all()
        )
    chunks = db.scalars(
        select(PatientChunk).where(PatientChunk.patient_id == patient_id)
    ).all()
    ranked = sorted(
        chunks, key=lambda c: cosine(list(c.embedding), query_vector), reverse=True
    )
    return ranked[:k]


def _ready_guidelines():
    """Chunks of active, fully-indexed guides only — a half-indexed 1000-page
    upload must not answer until its last page is embedded."""
    return (
        select(GuidelineChunk)
        .join(GuidelineDoc, GuidelineChunk.doc_id == GuidelineDoc.id)
        .where(GuidelineDoc.active.is_(True), GuidelineDoc.index_status == "ready")
    )


def retrieve_guidelines(
    db: Session, *, query_vector: list[float], k: int = 8
) -> list[GuidelineChunk]:
    if _is_postgres(db):
        return list(
            db.scalars(
                _ready_guidelines()
                .order_by(GuidelineChunk.embedding.cosine_distance(query_vector))
                .limit(k)
            ).all()
        )
    chunks = db.scalars(_ready_guidelines()).all()
    ranked = sorted(
        chunks, key=lambda c: cosine(list(c.embedding), query_vector), reverse=True
    )
    return ranked[:k]
