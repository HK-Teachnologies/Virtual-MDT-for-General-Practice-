"""0016 Optional patient measurements (weight, height)."""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("patients") as batch:
        batch.add_column(sa.Column("weight_kg", sa.Float(), nullable=True))
        batch.add_column(sa.Column("height_cm", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("patients") as batch:
        batch.drop_column("height_cm")
        batch.drop_column("weight_kg")
