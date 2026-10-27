"""Patient one-time login codes."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_otps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=True),
        sa.Column("used", sa.Boolean, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_patient_otps_patient_id", "patient_otps", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_otps_patient_id", table_name="patient_otps")
    op.drop_table("patient_otps")
