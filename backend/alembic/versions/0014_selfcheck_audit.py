"""0014 Self-check audit: new item fields + removed safety-panel points."""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brief_items") as batch:
        batch.add_column(sa.Column("source_type", sa.String(32), nullable=True))
        batch.add_column(sa.Column("question", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("urgent", sa.Boolean(), nullable=False, server_default="false")
        )
        batch.add_column(sa.Column("selfcheck_reason", sa.Text(), nullable=True))
    with op.batch_alter_table("brief_runs") as batch:
        batch.add_column(sa.Column("removed_points", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("brief_runs") as batch:
        batch.drop_column("removed_points")
    with op.batch_alter_table("brief_items") as batch:
        batch.drop_column("selfcheck_reason")
        batch.drop_column("urgent")
        batch.drop_column("question")
        batch.drop_column("source_type")
