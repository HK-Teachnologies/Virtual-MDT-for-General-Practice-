"""0019 Per-visit patient-safe summary ({en, sw, lg}) for the portal."""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("visits") as batch:
        batch.add_column(sa.Column("patient_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("visits") as batch:
        batch.drop_column("patient_summary")
