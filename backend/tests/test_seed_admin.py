import os
import uuid

import pytest
from sqlalchemy import func, select

import add_admin
from app.db.session import SessionLocal
from app.users.models import User


@pytest.fixture
def admin_env(monkeypatch):
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    return email


def test_seed_admin_idempotent(client, admin_env):
    assert add_admin.main() == 0
    assert add_admin.main() == 0
    db = SessionLocal()
    try:
        users = db.scalars(select(User).where(User.email == admin_env)).all()
        assert len(users) == 1
        assert users[0].role == "admin"
    finally:
        db.close()


def test_seed_admin_skips_without_env(client, monkeypatch):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(User))
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert add_admin.main() == 0
    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(User))
    assert after == before
