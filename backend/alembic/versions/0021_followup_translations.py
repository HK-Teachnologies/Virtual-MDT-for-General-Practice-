"""0021 Follow-up question translations ({en, sw, lg}) for the portal."""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("follow_ups") as batch:
        batch.add_column(sa.Column("question_i18n", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("follow_ups") as batch:
        batch.drop_column("question_i18n")
