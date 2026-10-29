"""0013 Persist brief safety panels (interactions + overdue checks)."""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brief_runs") as batch:
        batch.add_column(sa.Column("interactions", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("overdue_checks", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("brief_runs") as batch:
        batch.drop_column("overdue_checks")
        batch.drop_column("interactions")
