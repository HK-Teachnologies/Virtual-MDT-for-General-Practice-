"""0015 Guideline chunk pages + validated citation labels on brief items."""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("guideline_chunks") as batch:
        batch.add_column(sa.Column("page_start", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("page_end", sa.Integer(), nullable=True))
    with op.batch_alter_table("brief_items") as batch:
        batch.add_column(sa.Column("cited_labels", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("brief_items") as batch:
        batch.drop_column("cited_labels")
    with op.batch_alter_table("guideline_chunks") as batch:
        batch.drop_column("page_end")
        batch.drop_column("page_start")
