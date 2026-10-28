"""0007 MDT brief runs, transcriptions, guidelines, and vector chunks.

Postgres gets a real pgvector column (the db image ships the extension);
SQLite (test suite) gets a JSON list instead. Retrieval code branches on
the same dialect check.
"""

revision = "0007"
down_revision = "0006"

import sqlalchemy as sa
from alembic import op

EMBED_DIM = 1536


def _embedding_type():
    if op.get_bind().dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector

        return Vector(EMBED_DIM)
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    embedding = _embedding_type()

    op.create_table(
        "brief_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("current_step", sa.String(255), nullable=False, server_default="Queued"),
        sa.Column("model", sa.String(255), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(255), nullable=False, server_default="v1"),
        sa.Column("specialties", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_brief_runs_patient_id", "brief_runs", ["patient_id"])

    op.create_table(
        "brief_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("brief_runs.id"), nullable=False),
        sa.Column("specialty", sa.String(255), nullable=False, server_default=""),
        sa.Column("concern", sa.Text(), nullable=False, server_default=""),
        sa.Column("citation", sa.Text(), nullable=False, server_default=""),
        sa.Column("certainty", sa.String(32), nullable=False, server_default="low"),
        sa.Column("status", sa.String(32), nullable=False, server_default="suggested"),
        sa.Column("edited_text", sa.Text(), nullable=True),
    )
    op.create_index("ix_brief_items_run_id", "brief_items", ["run_id"])

    op.create_table(
        "transcriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("attachment_id", sa.String(36), sa.ForeignKey("attachments.id"), nullable=False, unique=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("model", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "guideline_docs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "guideline_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("guideline_docs.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding, nullable=False),
    )
    op.create_index("ix_guideline_chunks_doc_id", "guideline_chunks", ["doc_id"])

    op.create_table(
        "patient_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_patient_chunks_patient_id", "patient_chunks", ["patient_id"])


def downgrade() -> None:
    for table, index, columns in [
        ("patient_chunks", "ix_patient_chunks_patient_id", ["patient_id"]),
        ("guideline_chunks", "ix_guideline_chunks_doc_id", ["doc_id"]),
        ("brief_items", "ix_brief_items_run_id", ["run_id"]),
        ("brief_runs", "ix_brief_runs_patient_id", ["patient_id"]),
    ]:
        op.drop_index(index, table_name=table)
    for table in [
        "patient_chunks",
        "guideline_chunks",
        "guideline_docs",
        "transcriptions",
        "brief_items",
        "brief_runs",
    ]:
        op.drop_table(table)
