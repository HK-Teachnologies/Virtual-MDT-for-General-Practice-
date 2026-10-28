"""0011 Specialties, review routing, and specialist responses."""

revision = "0011"
down_revision = "0010"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "specialties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "specialty_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("specialty_id", sa.String(36), sa.ForeignKey("specialties.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("specialty_id", "user_id", name="uq_specialty_member"),
    )
    op.create_index("ix_specialty_members_specialty_id", "specialty_members", ["specialty_id"])
    op.create_index("ix_specialty_members_user_id", "specialty_members", ["user_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("brief_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reviews_patient_id", "reviews", ["patient_id"])
    op.create_index("ix_reviews_requested_by", "reviews", ["requested_by"])

    op.create_table(
        "review_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("specialty_id", sa.String(36), sa.ForeignKey("specialties.id"), nullable=True),
        sa.Column("emailed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("review_id", "user_id", name="uq_review_recipient"),
    )
    op.create_index("ix_review_recipients_review_id", "review_recipients", ["review_id"])

    op.create_table(
        "review_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("audio_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_review_responses_review_id", "review_responses", ["review_id"])


def downgrade() -> None:
    for table, index in [
        ("review_responses", "ix_review_responses_review_id"),
        ("review_recipients", "ix_review_recipients_review_id"),
        ("reviews", "ix_reviews_requested_by"),
        ("reviews", "ix_reviews_patient_id"),
        ("specialty_members", "ix_specialty_members_user_id"),
        ("specialty_members", "ix_specialty_members_specialty_id"),
    ]:
        op.drop_index(index, table_name=table)
    for table in [
        "review_responses",
        "review_recipients",
        "reviews",
        "specialty_members",
        "specialties",
    ]:
        op.drop_table(table)
