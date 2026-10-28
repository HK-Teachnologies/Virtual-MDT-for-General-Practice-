"""0008 Keep the original guideline file for staff download/audit."""

revision = "0008"
down_revision = "0007"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "guideline_docs", sa.Column("stored_path", sa.String(512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("guideline_docs", "stored_path")
