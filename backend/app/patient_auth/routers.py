import hashlib
import hmac
import json
import logging
import secrets
import smtplib
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
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


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Hand a message to SMTP. Returns True when accepted; never raises —
    callers treat notification mail as best-effort and only log failures."""
    if not settings.smtp_host:
        logger.info("Email skipped (SMTP not configured - dev mode): %s", subject)
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except Exception as exc:
        logger.warning("Email to %s failed (%s)", to_email, exc)
        return False
    return True


def _send_otp_email(to_email: str, code: str) -> None:
    """Email the code; always log it too (dev/demo use made-up addresses).

    The log line is gated by OTP_LOG_CODE (default on) so production can
    turn it off; codes are short-lived either way.
    """
    if settings.otp_log_code:
        logger.info("OTP for %s: %s", to_email, code)
    _send_email(
        to_email,
        "Your Virtual MDT sign-in code",
        f"Your Virtual MDT sign-in code is {code}. "
        f"It expires in {settings.otp_expire_minutes} minutes. "
        "If you did not request this, ignore this message.",
    )


def send_answer_notification(to_email: str) -> bool:
    """Tell a patient their doctor has answered: a sign-in nudge only, never
    clinical content — the question and answer stay inside the portal."""
    return _send_email(
        to_email,
        "Your doctor has answered your question",
        "Your doctor has answered the question you asked in the Virtual MDT "
        "patient portal. Sign in to read the answer. "
        "If you did not ask a question, ignore this message.",
    )


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


class MyReferralLetter(BaseModel):
    id: str
    destination_facility: str
    reason: str
    letter_text: str
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
    # Released referral letters, to show at any facility attended.
    referral_letters: list[MyReferralLetter] = []


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
    from app.mdt.models import ReferralLetter

    letters = (
        db.scalars(
            select(ReferralLetter)
            .where(
                ReferralLetter.patient_id == current.id,
                ReferralLetter.summary_status == "released",
            )
            .order_by(ReferralLetter.created_at)
        ).all()
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
        referral_letters=[
            MyReferralLetter(
                id=letter.id,
                destination_facility=letter.destination_facility,
                reason=letter.reason,
                letter_text=letter.letter_text,
                released_by_name=_staff_name(db, letter.released_by),
                released_at=letter.released_at,
            )
            for letter in letters
        ],
    )


PORTAL_CHAT_LANGS = ("en", "sw", "lg")

# Danger signs that skip the model entirely: the reply is a fixed urgent
# redirect, never a diagnosis. Matched case-insensitively against the
# English question (voice notes are translated first).
RED_FLAG_TERMS = (
    "bleeding",
    "bleed",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "breathing difficulty",
    "short of breath",
    "chest pain",
    "chest pressure",
    "unconscious",
    "fainted",
    "fainting",
    "seizure",
    "convulsion",
    "fit ",
    "poison",
    "overdose",
    "suicide",
    "kill myself",
    "burn",
    "broken bone",
    "fracture",
    "labour",
    "labor",
    "water broke",
    "severe headache",
    "worst headache",
    "vision loss",
    "cannot see",
    "high fever with rash",
    "stiff neck",
)

URGENT_REPLY = {
    "en": (
        "What you describe can be an emergency. Go to the nearest health "
        "facility or emergency unit now — do not wait for a reply here."
    ),
    "sw": (
        "Dalili ulizoeleza zinaweza kuwa za dharura. Nenda kwenye kituo cha "
        "afya kilicho karibu nawe sasa hivi — usisubiri jibu hapa."
    ),
    "lg": (
        "Ebyo by'ogambye biyinza okuba eby'akabenje. Genda mangu ku "
        "ddwaliro erisinga okuba okumpi naawe — tolindirira kuddamu wano."
    ),
}

PORTAL_CHAT_SYSTEM = """You are a friendly clinic guide inside a patient's own health portal.
You are NOT a doctor. Rules you must never break:
1. Never diagnose: never name a condition the patient might have.
2. Never prescribe, start, stop, or change any medicine or dose.
3. Answer ONLY from the provided record: released visit summaries, the overall
   message, the prescription list, and the clinic list. If the answer is not
   there, say you cannot answer that here and point them to their doctor.
4. Medication questions: explain what is written (name, dose, timing as
   recorded). Any change, side effect, or missed dose means asking the doctor.
5. Which clinic to visit: match the concern to the clinic names and
   descriptions given. If none fits, suggest the general outpatient clinic or
   asking at reception. Never invent facilities.
6. Reply in the requested language, in short plain words (2-4 sentences), and
   always close by inviting them to visit their clinic or ask their doctor if
   worried.
Return JSON: {"reply": "<your answer>"}."""


class PortalChatReply(BaseModel):
    reply: str
    lang: str
    question_original: str
    question_en: str
    urgent: bool = False


def _has_red_flags(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in RED_FLAG_TERMS)


@router.post("/chat", response_model=PortalChatReply)
def portal_chat(
    message: str = Form(""),
    lang: str = Form("en"),
    audio: UploadFile | None = File(None),
    current: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Patient guide chat: plain answers from released content, never a
    diagnosis. Voice notes (Luganda/Kiswahili/English) are transcribed first;
    danger signs get a fixed urgent redirect without any model call."""
    from app.clinics.models import Clinic
    from app.llm.client import complete_json, transcribe_to_english
    from app.mdt.models import BriefRun
    from app.patients.models import Visit, VisitSection

    if lang not in PORTAL_CHAT_LANGS:
        raise HTTPException(
            status_code=400, detail="lang must be one of: en, sw, lg"
        )
    question_original = message.strip()
    question_en = message.strip()
    if audio is not None and audio.filename:
        suffix = Path(audio.filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio.file.read())
            path = tmp.name
        try:
            original, english = transcribe_to_english(path)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Voice transcription failed: {exc}"
            )
        finally:
            Path(path).unlink(missing_ok=True)
        if not question_original:
            question_original = original
        if english.strip():
            question_en = english.strip()
    if not question_en:
        raise HTTPException(status_code=400, detail="Ask with text or a voice note")
    if _has_red_flags(question_en):
        return PortalChatReply(
            reply=URGENT_REPLY.get(lang, URGENT_REPLY["en"]),
            lang=lang,
            question_original=question_original,
            question_en=question_en,
            urgent=True,
        )

    visits = (
        db.scalars(
            select(Visit)
            .where(Visit.patient_id == current.id)
            .order_by(Visit.visit_date)
        ).all()
    )
    summaries = []
    for visit in visits:
        if (visit.summary_status or "draft") != "released":
            continue
        stored = dict(visit.patient_summary or {})
        text = str(stored.get(lang, "") or stored.get("en", "")).strip()
        if text:
            summaries.append({"date": str(visit.visit_date), "text": text})
    run = (
        db.scalars(
            select(BriefRun)
            .where(BriefRun.patient_id == current.id, BriefRun.status == "ready")
            .order_by(BriefRun.created_at.desc())
        ).first()
    )
    overall = ""
    if run is not None and (run.summary_status or "draft") == "released":
        stored = dict(run.patient_summary or {})
        overall = str(stored.get(lang, "") or stored.get("en", "")).strip()
    prescriptions = [
        {"date": str(visit.visit_date), "text": section.content.strip()}
        for visit in visits
        for section in db.scalars(
            select(VisitSection).where(
                VisitSection.visit_id == visit.id,
                VisitSection.section == "prescription",
            )
        ).all()
        if section.content.strip()
    ]
    clinics = [
        {"name": clinic.name, "description": clinic.description or ""}
        for clinic in db.scalars(
            select(Clinic).where(Clinic.active.is_(True)).order_by(Clinic.name)
        ).all()
    ]
    try:
        raw = complete_json(
            system=PORTAL_CHAT_SYSTEM,
            user=json.dumps(
                {
                    "question": question_en,
                    "language": lang,
                    "released_summaries": summaries,
                    "overall_message": overall,
                    "prescriptions": prescriptions,
                    "clinics": clinics,
                }
            ),
            kind="portal_chat",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"The guide has no answer right now: {exc}"
        )
    reply = str(raw.get("reply", "")).strip()
    if not reply:
        raise HTTPException(status_code=502, detail="The guide has no answer right now")
    return PortalChatReply(
        reply=reply,
        lang=lang,
        question_original=question_original,
        question_en=question_en,
        urgent=False,
    )
