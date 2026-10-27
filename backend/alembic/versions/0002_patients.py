"""Patients, visits and attachments tables."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("sex", sa.String(32), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_patients_phone", "patients", ["phone"], unique=True)
    op.create_index("ix_patients_email", "patients", ["email"], unique=True)
    op.create_table(
        "visits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("visit_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("source", sa.String(32), nullable=False, server_default="typed"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_visits_patient_id", "visits", ["patient_id"])
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visit_id", sa.String(36), sa.ForeignKey("visits.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_attachments_visit_id", "attachments", ["visit_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_visit_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_visits_patient_id", table_name="visits")
    op.drop_table("visits")
    op.drop_index("ix_patients_email", table_name="patients")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_table("patients")
