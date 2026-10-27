import os
from pathlib import Path

# Point at a scratch sqlite DB before the app is imported (settings load on import).
DB_PATH = Path(__file__).parent / "test_tmp.db"
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
