"""0017 Doctor -> patient follow-up questions."""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("asked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_audio_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_follow_ups_patient_id", "follow_ups", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_follow_ups_patient_id", table_name="follow_ups")
    op.drop_table("follow_ups")
