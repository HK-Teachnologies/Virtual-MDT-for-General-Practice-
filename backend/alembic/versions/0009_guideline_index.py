"""0009 Guideline indexing status + vector indexes for 1000+ page documents.

Existing guideline rows already have embeddings, so they default to ready.
The HNSW indexes keep retrieval fast once a big guideline means thousands
of chunk rows (Postgres only — SQLite has no vector index).
"""

revision = "0009"
down_revision = "0008"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "guideline_docs",
        sa.Column("index_status", sa.String(32), nullable=False, server_default="ready"),
    )
    op.add_column(
        "guideline_docs",
        sa.Column("index_error", sa.Text(), nullable=False, server_default=""),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_guideline_chunks_embedding "
            "ON guideline_chunks USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_patient_chunks_embedding "
            "ON patient_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_guideline_chunks_embedding")
        op.execute("DROP INDEX IF EXISTS ix_patient_chunks_embedding")
    op.drop_column("guideline_docs", "index_error")
    op.drop_column("guideline_docs", "index_status")
