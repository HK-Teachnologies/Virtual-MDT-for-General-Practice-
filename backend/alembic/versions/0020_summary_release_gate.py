"""0020 Clinician release gate for patient-facing summaries."""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def _add_gate(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(
            sa.Column("summary_status", sa.String(16), server_default="draft")
        )
        batch.add_column(sa.Column("released_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))


def _drop_gate(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_column("released_at")
        batch.drop_column("released_by")
        batch.drop_column("summary_status")


def upgrade() -> None:
    _add_gate("visits")
    _add_gate("brief_runs")


def downgrade() -> None:
    _drop_gate("visits")
    _drop_gate("brief_runs")
