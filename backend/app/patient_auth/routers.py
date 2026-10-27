import hashlib
import hmac
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/patient-auth/verify")
ALGORITHM = "HS256"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _send_otp_email(to_email: str, code: str) -> None:
    """Email the code, or log it when SMTP is not configured (dev/demo)."""
    if not settings.smtp_host:
        print(f"OTP for {to_email}: {code} (SMTP not configured - dev mode)", flush=True)
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
        print(f"OTP email to {to_email} failed ({exc}) - code was: {code}", flush=True)


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
