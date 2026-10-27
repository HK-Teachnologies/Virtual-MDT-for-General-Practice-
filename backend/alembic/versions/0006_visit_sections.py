"""Visit clinical sections (lab, imaging, ...)."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visit_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visit_id", sa.String(36), sa.ForeignKey("visits.id"), nullable=False),
        sa.Column("section", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_visit_sections_visit_id", "visit_sections", ["visit_id"])


def downgrade() -> None:
    op.drop_index("ix_visit_sections_visit_id", table_name="visit_sections")
    op.drop_table("visit_sections")
