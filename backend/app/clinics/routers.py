from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clinics.models import Clinic
from app.clinics.schemas import ClinicCreate, ClinicRead, ClinicUpdate
from app.db.session import get_db
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _require_admin(current: User) -> None:
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )


@router.get("", response_model=list[ClinicRead])
def list_clinics(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(select(Clinic).where(Clinic.active.is_(True)).order_by(Clinic.name)).all()


@router.post("", response_model=ClinicRead, status_code=status.HTTP_201_CREATED)
def create_clinic(
    data: ClinicCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    clinic = Clinic(
        name=data.name.strip(), description=data.description, created_by=current.id
    )
    db.add(clinic)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Clinic already exists")
    db.refresh(clinic)
    return clinic


@router.patch("/{clinic_id}", response_model=ClinicRead)
def update_clinic(
    clinic_id: str,
    data: ClinicUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    clinic = db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(clinic, field, value if field != "name" or value is None else value.strip())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Clinic already exists")
    db.refresh(clinic)
    return clinic
