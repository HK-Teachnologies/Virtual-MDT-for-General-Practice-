"""0024 Patient -> doctor questions asked in the portal."""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("question_original", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("answered_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_patient_questions_patient_id", "patient_questions", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_questions_patient_id", table_name="patient_questions")
    op.drop_table("patient_questions")
