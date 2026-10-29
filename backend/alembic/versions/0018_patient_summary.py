"""0018 Patient-safe brief summary ({en, sw, lg}) for the portal."""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brief_runs") as batch:
        batch.add_column(sa.Column("patient_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("brief_runs") as batch:
        batch.drop_column("patient_summary")
