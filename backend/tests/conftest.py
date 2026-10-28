import os
from pathlib import Path

# Point at a scratch sqlite DB before the app is imported (settings load on import).
DB_PATH = Path(__file__).parent / "test_tmp.db"
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
# Background AI runs inline with a deterministic echo provider: no Redis,
# no network, no API keys needed for the suite.
os.environ.setdefault("LLM_PROVIDER", "echo")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.users.models import User  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()


def admin_token(client: TestClient, email: str = "admin@example.com") -> str:
    """Bootstrap an admin directly in the DB and return its login token."""
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == email)):
            db.add(
                User(
                    email=email,
                    hashed_password=hash_password("admin123"),
                    full_name="Admin",
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()
    r = client.post(
        "/api/auth/login", data={"username": email, "password": "admin123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
