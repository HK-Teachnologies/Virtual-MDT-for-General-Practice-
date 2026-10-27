"""Clinics master table + visit classification, seeded with defaults."""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DEFAULT_CLINICS = [
    ("OPD", "Outpatient department"),
    ("HIV Clinic", "HIV care and treatment"),
    ("NCD Clinic", "Non-communicable diseases: hypertension, diabetes"),
    ("TB Clinic", "Tuberculosis screening and treatment"),
    ("ANC", "Antenatal care"),
    ("Mental Health", "Mental health reviews"),
    ("Pharmacy", "Pharmacy reviews and refills"),
]


def upgrade() -> None:
    op.create_table(
        "clinics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=True),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_clinics_name", "clinics", ["name"], unique=True)
    # Batch mode so the FK also applies on SQLite (used by the test suite).
    with op.batch_alter_table("visits") as batch_op:
        batch_op.add_column(sa.Column("clinic_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_visits_clinic_id", "clinics", ["clinic_id"], ["id"]
        )
    op.bulk_insert(
        sa.table(
            "clinics",
            sa.column("id", sa.String(36)),
            sa.column("name", sa.String(255)),
            sa.column("description", sa.Text),
            sa.column("active", sa.Boolean),
            sa.column("created_by", sa.String(36)),
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "active": True,
                "created_by": None,
            }
            for name, description in DEFAULT_CLINICS
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table("visits") as batch_op:
        batch_op.drop_constraint("fk_visits_clinic_id", type_="foreignkey")
        batch_op.drop_column("clinic_id")
    op.drop_index("ix_clinics_name", table_name="clinics")
    op.drop_table("clinics")
