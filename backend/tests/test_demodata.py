import os

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.patients.models import Patient, Visit

from .conftest import admin_token

import add_demodata


def test_demodata_flag_off_skips(client: TestClient, monkeypatch):
    admin_token(client)
    monkeypatch.setenv("ADD_DEMO_DATA", "false")
    assert add_demodata.main() == 0
    with SessionLocal() as db:
        assert (
            db.scalar(select(Patient).where(Patient.email == "demo-a@example.com"))
            is None
        )


def test_demodata_seeds_and_is_idempotent(client: TestClient, monkeypatch):
    admin_token(client)
    monkeypatch.setenv("ADD_DEMO_DATA", "true")
    assert add_demodata.main() == 0
    with SessionLocal() as db:
        patient = db.scalar(
            select(Patient).where(Patient.email == "demo-a@example.com")
        )
        assert patient is not None
        assert patient.full_name == "Demo Patient A"
        visits = (
            db.scalars(select(Visit).where(Visit.patient_id == patient.id)).all()
        )
        assert len(visits) == 4
        assert {v.clinic_id for v in visits}  # classified into clinics
    # Second run changes nothing.
    assert add_demodata.main() == 0
    with SessionLocal() as db:
        visits = db.scalars(
            select(Visit).where(
                Visit.patient_id
                == db.scalar(
                    select(Patient.id).where(Patient.email == "demo-a@example.com")
                )
            )
        ).all()
        assert len(visits) == 4


def test_demodata_needs_no_admin_but_skips_without_users(
    client: TestClient, monkeypatch
):
    monkeypatch.setenv("ADD_DEMO_DATA", "true")
    # No users bootstrapped: script skips cleanly instead of crashing boot.
    assert add_demodata.main() == 0
