"""0022 Persistent referral letters with a clinician release gate."""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referral_letters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), index=True, nullable=False),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), index=True, nullable=False),
        sa.Column("destination_facility", sa.String(255), server_default=""),
        sa.Column("reason", sa.Text(), server_default=""),
        sa.Column("additional_note", sa.Text(), server_default=""),
        sa.Column("letter_text", sa.Text(), server_default=""),
        sa.Column("summary_status", sa.String(16), server_default="draft"),
        sa.Column("released_by", sa.String(36), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("referral_letters")
