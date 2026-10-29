import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.patient_auth.models import OtpCode
from app.patient_auth.schemas import OtpRequest, OtpSent, OtpVerify, PatientToken
from app.patients.models import Patient
from app.patients.routers import load_patient_detail
from app.patients.schemas import PatientRead
from app.users.models import User

router = APIRouter()

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/patient-auth/verify")
ALGORITHM = "HS256"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _send_otp_email(to_email: str, code: str) -> None:
    """Email the code; always log it too (dev/demo use made-up addresses).

    The log line is gated by OTP_LOG_CODE (default on) so production can
    turn it off; codes are short-lived either way.
    """
    if settings.otp_log_code:
        logger.info("OTP for %s: %s", to_email, code)
    if not settings.smtp_host:
        logger.info("OTP email skipped (SMTP not configured - dev mode)")
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = "Your Virtual MDT sign-in code"
    message.set_content(
        f"Your Virtual MDT sign-in code is {code}. "
        f"It expires in {settings.otp_expire_minutes} minutes. "
        "If you did not request this, ignore this message."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except Exception as exc:
        logger.warning("OTP email to %s failed (%s) - code was: %s", to_email, exc, code)


def _find_patient(db: Session, identifier: str):
    identifier = identifier.strip()
    return db.scalar(
        select(Patient).where(
            (Patient.email == identifier) | (Patient.phone == identifier)
        )
    )


def create_patient_token(patient_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"pid": patient_id, "role": "patient", "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def get_current_patient(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Patient:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise credentials_exception
    if payload.get("role") != "patient" or not isinstance(payload.get("pid"), str):
        raise credentials_exception
    patient = db.get(Patient, payload["pid"])
    if patient is None:
        raise credentials_exception
    return patient


@router.post("/request", response_model=OtpSent)
def request_code(data: OtpRequest, db: Session = Depends(get_db)):
    # Always answer the same way so identifiers can't be enumerated.
    patient = _find_patient(db, data.identifier)
    if patient is None or not patient.email:
        return OtpSent()
    db.query(OtpCode).filter(
        OtpCode.patient_id == patient.id, OtpCode.used.is_(False)
    ).update({OtpCode.used: True})
    code = f"{100000 + secrets.randbelow(900000):06d}"
    db.add(
        OtpCode(
            patient_id=patient.id,
            code_hash=_hash_code(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.otp_expire_minutes),
        )
    )
    db.commit()
    _send_otp_email(patient.email, code)
    return OtpSent()


@router.post("/verify", response_model=PatientToken)
def verify_code(data: OtpVerify, db: Session = Depends(get_db)):
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid identifier or code",
    )
    patient = _find_patient(db, data.identifier)
    if patient is None:
        raise invalid
    code = (
        db.scalars(
            select(OtpCode)
            .where(OtpCode.patient_id == patient.id, OtpCode.used.is_(False))
            .order_by(OtpCode.created_at.desc())
        ).first()
    )
    if code is None or code.attempts >= settings.otp_max_attempts:
        raise invalid
    now = datetime.now(timezone.utc)
    expires = code.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now or not hmac.compare_digest(
        code.code_hash, _hash_code(data.code.strip())
    ):
        code.attempts += 1
        db.commit()
        raise invalid
    code.used = True
    db.commit()
    return PatientToken(access_token=create_patient_token(patient.id))


@router.get("/me", response_model=PatientRead)
def read_own_record(
    current: Patient = Depends(get_current_patient), db: Session = Depends(get_db)
):
    return load_patient_detail(db, current.id)


class MySummaryVisit(BaseModel):
    visit_id: str
    date: str
    en: str = ""
    sw: str = ""
    lg: str = ""
    ready: bool = False
    released_by_name: str | None = None
    released_at: datetime | None = None


class MySummary(BaseModel):
    run_id: str | None = None
    completed_at: datetime | None = None
    # Overall message from the latest released brief, when a review exists.
    summary: dict = {}
    summary_released_by_name: str | None = None
    summary_released_at: datetime | None = None
    # Released per-visit lines only — drafts never reach the patient.
    visits: list[MySummaryVisit] = []


def _staff_name(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return (user.full_name or user.email) if user else None


@router.get("/my-summary", response_model=MySummary)
def read_own_summary(
    current: Patient = Depends(get_current_patient), db: Session = Depends(get_db)
):
    """Portal summary: released per-visit lines plus the released brief
    overall when present. Drafts are never served — and reading never
    generates anything, so a visit cannot reach the patient unreviewed."""
    from app.mdt.models import BriefRun
    from app.patients.models import Visit

    rows = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == current.id)
            .order_by(Visit.visit_date)
        ).all()
    )
    visits = []
    for visit in rows:
        released = (visit.summary_status or "draft") == "released"
        stored = dict(visit.patient_summary or {}) if released else {}
        visits.append(
            MySummaryVisit(
                visit_id=visit.id,
                date=str(visit.visit_date),
                en=str(stored.get("en", "")),
                sw=str(stored.get("sw", "")),
                lg=str(stored.get("lg", "")),
                ready=released,
                released_by_name=_staff_name(db, visit.released_by)
                if released
                else None,
                released_at=visit.released_at if released else None,
            )
        )
    run = (
        db.scalars(
            select(BriefRun)
            .where(BriefRun.patient_id == current.id, BriefRun.status == "ready")
            .order_by(BriefRun.created_at.desc())
        ).first()
    )
    overall_released = (
        run is not None and (run.summary_status or "draft") == "released"
    )
    return MySummary(
        run_id=run.id if run else None,
        completed_at=run.completed_at if run else None,
        summary=dict(run.patient_summary or {}) if overall_released else {},
        summary_released_by_name=_staff_name(db, run.released_by)
        if overall_released
        else None,
        summary_released_at=run.released_at if overall_released else None,
        visits=visits,
    )
