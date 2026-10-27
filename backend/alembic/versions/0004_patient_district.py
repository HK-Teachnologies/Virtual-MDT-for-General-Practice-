"""Patient district field (area of residence stays in address)."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("district", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "district")
