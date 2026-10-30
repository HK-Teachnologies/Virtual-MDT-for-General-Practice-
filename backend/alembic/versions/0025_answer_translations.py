"""0025 Clinician-checked answer translations on patient questions."""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("patient_questions") as batch:
        batch.add_column(sa.Column("answer_i18n", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("patient_questions") as batch:
        batch.drop_column("answer_i18n")
