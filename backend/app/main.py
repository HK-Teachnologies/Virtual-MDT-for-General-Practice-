from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.core.config import settings
from app.clinics import models as clinic_models  # noqa: F401 — register for create_all
from app.clinics import routers as clinic_routers
from app.health import routers as health_routers
from app.patient_auth import models as otp_models  # noqa: F401 — register for create_all
from app.patient_auth import routers as patient_auth_routers
from app.patients import routers as patient_routers
from app.profiles import routers as profile_routers
from app.users import routers as auth_routers


def run_migrations() -> None:
    ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Virtual MDT API", lifespan=lifespan)
app.include_router(health_routers.router, prefix="/api")
app.include_router(auth_routers.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile_routers.router, prefix="/api/profile", tags=["profile"])
app.include_router(patient_routers.router, prefix="/api/patients", tags=["patients"])
app.include_router(
    patient_auth_routers.router, prefix="/api/patient-auth", tags=["patient-auth"]
)
app.include_router(clinic_routers.router, prefix="/api/clinics", tags=["clinics"])
