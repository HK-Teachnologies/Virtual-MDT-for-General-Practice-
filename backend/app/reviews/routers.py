import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.llm import client as llm
from app.patients.models import Patient
from app.reviews.models import REVIEW_STATUSES, Review, ReviewRecipient, ReviewResponse
from app.reviews.schemas import (
    RecipientRead,
    ResponseRead,
    ReviewCreate,
    ReviewRead,
    ReviewUpdate,
)
from app.specialties.models import Specialty, SpecialtyMember
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Review notification email. Returns False (and logs) when SMTP is
    unset or sending fails — the review itself is never blocked."""
    link_hint = body
    if not settings.smtp_host:
        print(
            f"REVIEW email to {to_email} [{subject}]: {link_hint} (SMTP not configured)",
            flush=True,
        )
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
        return True
    except Exception as exc:
        print(f"REVIEW email to {to_email} failed ({exc})", flush=True)
        return False


def _review_link(review_id: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/reviews/{review_id}"


def _can_see(db: Session, review: Review, user: User) -> bool:
    if user.role == "admin" or review.requested_by == user.id:
        return True
    return (
        db.scalar(
            select(ReviewRecipient).where(
                ReviewRecipient.review_id == review.id,
                ReviewRecipient.user_id == user.id,
            )
        )
        is not None
    )


def _read(db: Session, review: Review) -> ReviewRead:
    patient = db.get(Patient, review.patient_id)
    requester = db.get(User, review.requested_by)
    recipient_rows = db.scalars(
        select(ReviewRecipient).where(ReviewRecipient.review_id == review.id)
    ).all()
    recipients = []
    for row in recipient_rows:
        user = db.get(User, row.user_id)
        specialty = db.get(Specialty, row.specialty_id) if row.specialty_id else None
        recipients.append(
            RecipientRead(
                id=row.id,
                user_id=row.user_id,
                email=user.email if user else "",
                full_name=user.full_name if user else None,
                specialty_id=row.specialty_id,
                specialty_name=specialty.name if specialty else None,
                emailed=row.emailed,
            )
        )
    response_rows = (
        db.scalars(
            select(ReviewResponse)
            .where(ReviewResponse.review_id == review.id)
            .order_by(ReviewResponse.created_at)
        ).all()
    )
    responses = []
    for row in response_rows:
        author = db.get(User, row.author_id)
        responses.append(
            ResponseRead(
                id=row.id,
                author_id=row.author_id,
                author_email=author.email if author else "",
                author_name=author.full_name if author else None,
                text=row.text,
                has_audio=bool(row.audio_path),
                has_image=bool(row.image_path),
                created_at=row.created_at,
            )
        )
    return ReviewRead(
        id=review.id,
        patient_id=review.patient_id,
        patient_name=patient.full_name if patient else "",
        requested_by=review.requested_by,
        requester_email=requester.email if requester else "",
        message=review.message,
        brief_snapshot=review.brief_snapshot or {},
        status=review.status,
        created_at=review.created_at,
        closed_at=review.closed_at,
        recipients=recipients,
        responses=responses,
        response_count=len(responses),
    )


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def request_review(
    data: ReviewCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Default recipients: every member of each chosen specialty.
    # Explicit user_ids add hand-picked specialists on top.
    targets: dict[str, str | None] = {}
    for specialty_id in data.specialty_ids:
        specialty = db.get(Specialty, specialty_id)
        if specialty is None or not specialty.active:
            raise HTTPException(
                status_code=400, detail="Unknown or retired specialty selected"
            )
        member_ids = db.scalars(
            select(SpecialtyMember.user_id).where(
                SpecialtyMember.specialty_id == specialty.id
            )
        ).all()
        for user_id in member_ids:
            targets.setdefault(user_id, specialty.id)
    for user_id in data.user_ids:
        targets.setdefault(user_id, None)
    targets.pop(current.id, None)  # never notify yourself
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No recipients: pick a specialty with members or choose people",
        )
    for user_id in targets:
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=400, detail="Unknown user selected")

    review = Review(
        patient_id=patient.id,
        requested_by=current.id,
        message=data.message.strip(),
        brief_snapshot=data.brief.model_dump(),
        status="pending",
    )
    db.add(review)
    db.flush()
    for user_id, specialty_id in targets.items():
        user = db.get(User, user_id)
        emailed = _send_email(
            user.email,
            f"Review requested: {patient.full_name}",
            f"{current.full_name or current.email} asks for your input on "
            f"{patient.full_name}.\n\n{data.message.strip()}\n\n"
            f"Open the review: {_review_link(review.id)}",
        )
        db.add(
            ReviewRecipient(
                review_id=review.id,
                user_id=user_id,
                specialty_id=specialty_id,
                emailed=emailed,
            )
        )
    db.commit()
    db.refresh(review)
    return _read(db, review)


@router.get("/inbox", response_model=list[ReviewRead])
def inbox(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Reviews assigned to the signed-in user."""
    reviews = db.scalars(
        select(Review)
        .join(ReviewRecipient, ReviewRecipient.review_id == Review.id)
        .where(ReviewRecipient.user_id == current.id)
        .order_by(Review.created_at.desc())
    ).all()
    return [_read(db, r) for r in reviews]


@router.get("/requested", response_model=list[ReviewRead])
def requested(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Reviews the signed-in user asked for, with their responses."""
    reviews = db.scalars(
        select(Review)
        .where(Review.requested_by == current.id)
        .order_by(Review.created_at.desc())
    ).all()
    return [_read(db, r) for r in reviews]


@router.get("/{review_id}", response_model=ReviewRead)
def read_review(
    review_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if not _can_see(db, review, current):
        raise HTTPException(status_code=403, detail="Not part of this review")
    return _read(db, review)


@router.post("/{review_id}/responses", response_model=ResponseRead)
def respond(
    review_id: str,
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
    image: UploadFile | None = File(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reply in text, by voice recording, with a photo attached, or any mix.
    Voice is transcribed so the response is always readable (and listenable
    when audio was kept)."""
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if not _can_see(db, review, current):
        raise HTTPException(status_code=403, detail="Not part of this review")
    if review.status == "closed":
        raise HTTPException(status_code=400, detail="Review is closed")

    body = text.strip()
    audio_path: str | None = None
    if audio is not None:
        raw = audio.file.read()
        if raw:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(audio.filename or "voice").name)
            stored = f"{uuid.uuid4().hex}_{safe}"
            voice_dir = Path(settings.upload_dir) / "review_audio"
            voice_dir.mkdir(parents=True, exist_ok=True)
            (voice_dir / stored).write_bytes(raw)
            audio_path = str(voice_dir / stored)
            if not body:
                try:
                    body = llm.transcribe_audio(audio_path).strip()
                except llm.LLMError as exc:
                    raise HTTPException(
                        status_code=502, detail=f"Voice transcription failed: {exc}"
                    )
    image_path: str | None = None
    image_content_type: str | None = None
    if image is not None:
        raw_image = image.file.read()
        if raw_image:
            if not (image.content_type or "").startswith("image/"):
                raise HTTPException(
                    status_code=400, detail="Only image files can be attached"
                )
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(image.filename or "photo").name)
            stored = f"{uuid.uuid4().hex}_{safe}"
            image_dir = Path(settings.upload_dir) / "review_images"
            image_dir.mkdir(parents=True, exist_ok=True)
            (image_dir / stored).write_bytes(raw_image)
            image_path = str(image_dir / stored)
            image_content_type = image.content_type
    if not body and audio_path is None and image_path is None:
        raise HTTPException(
            status_code=400,
            detail="Write a response or attach a voice recording or image",
        )
    response = ReviewResponse(
        review_id=review.id,
        author_id=current.id,
        text=body,
        audio_path=audio_path,
        image_path=image_path,
        image_content_type=image_content_type,
    )
    db.add(response)
    if review.status == "pending":
        review.status = "responded"
    db.commit()
    db.refresh(response)

    requester = db.get(User, review.requested_by)
    if requester is not None and requester.id != current.id:
        patient = db.get(Patient, review.patient_id)
        _send_email(
            requester.email,
            f"Review response: {patient.full_name if patient else 'a patient'}",
            f"{current.full_name or current.email} responded.\n\n"
            f"Read it: {_review_link(review.id)}",
        )
    author = db.get(User, current.id)
    return ResponseRead(
        id=response.id,
        author_id=current.id,
        author_email=author.email if author else "",
        author_name=author.full_name if author else None,
        text=response.text,
        has_audio=bool(audio_path),
        has_image=bool(image_path),
        created_at=response.created_at,
    )


@router.get("/responses/{response_id}/audio")
def response_audio(
    response_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = db.get(ReviewResponse, response_id)
    if response is None or not response.audio_path:
        raise HTTPException(status_code=404, detail="No recording for this response")
    review = db.get(Review, response.review_id)
    if review is None or not _can_see(db, review, current):
        raise HTTPException(status_code=403, detail="Not part of this review")
    return FileResponse(response.audio_path, media_type="audio/webm")


@router.get("/responses/{response_id}/image")
def response_image(
    response_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = db.get(ReviewResponse, response_id)
    if response is None or not response.image_path:
        raise HTTPException(status_code=404, detail="No image for this response")
    review = db.get(Review, response.review_id)
    if review is None or not _can_see(db, review, current):
        raise HTTPException(status_code=403, detail="Not part of this review")
    return FileResponse(
        response.image_path,
        media_type=response.image_content_type or "application/octet-stream",
    )


@router.get("/for-patient/{patient_id}", response_model=list[ReviewRead])
def open_for_patient(
    patient_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Still-open reviews on one patient, newest first. Any staff viewing the
    record can see them — this is what blocks sending a duplicate review."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    rows = (
        db.scalars(
            select(Review)
            .where(Review.patient_id == patient_id, Review.status != "closed")
            .order_by(Review.created_at.desc())
        ).all()
    )
    return [_read(db, review) for review in rows]


@router.patch("/{review_id}", response_model=ReviewRead)
def close_review(
    review_id: str,
    data: ReviewUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.status != "closed":
        raise HTTPException(status_code=400, detail="Only 'closed' is supported")
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if current.role != "admin" and review.requested_by != current.id:
        raise HTTPException(
            status_code=403, detail="Only the requester or an admin can close"
        )
    review.status = "closed"
    review.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return _read(db, review)
