"""0010 Switch vector columns to the model server's 768-dim embeddings.

Existing chunk rows hold 1536-dim echo vectors that cannot cast to
vector(768), so they are cleared: guidelines are re-uploaded by an admin,
patient chunks rebuild on the next record edit. SQLite stores plain JSON
lists and needs no change.
"""

revision = "0010"
down_revision = "0009"

from alembic import op


def _swap(from_dim: int, to_dim: int) -> None:
    op.execute("DROP INDEX IF EXISTS ix_guideline_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_patient_chunks_embedding")
    op.execute("DELETE FROM guideline_chunks")
    op.execute("DELETE FROM patient_chunks")
    op.execute(
        "ALTER TABLE guideline_chunks "
        f"ALTER COLUMN embedding TYPE vector({to_dim})"
    )
    op.execute(
        "ALTER TABLE patient_chunks "
        f"ALTER COLUMN embedding TYPE vector({to_dim})"
    )
    op.execute(
        "CREATE INDEX ix_guideline_chunks_embedding "
        "ON guideline_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_patient_chunks_embedding "
        "ON patient_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _swap(1536, 768)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _swap(768, 1536)
