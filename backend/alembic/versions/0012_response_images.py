"""0012 Response image attachments on specialist reviews."""

revision = "0012"
down_revision = "0011"

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "review_responses",
        sa.Column("image_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "review_responses",
        sa.Column("image_content_type", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_responses", "image_content_type")
    op.drop_column("review_responses", "image_path")
