"""0023 Keep the original-language transcript of voice answers."""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("follow_ups") as batch:
        batch.add_column(sa.Column("answer_original", sa.Text(), server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("follow_ups") as batch:
        batch.drop_column("answer_original")
