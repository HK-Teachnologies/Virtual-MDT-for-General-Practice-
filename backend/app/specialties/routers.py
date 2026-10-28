from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.specialties.models import Specialty, SpecialtyMember
from app.specialties.schemas import (
    MemberAdd,
    SpecialtyCreate,
    SpecialtyRead,
    SpecialtyUpdate,
    UserRef,
)
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def _read(db: Session, specialty: Specialty, with_members: bool) -> SpecialtyRead:
    members: list[UserRef] = []
    if with_members:
        users = db.scalars(
            select(User)
            .join(SpecialtyMember, SpecialtyMember.user_id == User.id)
            .where(SpecialtyMember.specialty_id == specialty.id)
            .order_by(User.email)
        ).all()
        members = [UserRef.model_validate(u) for u in users]
    else:
        count = (
            db.scalar(
                select(func.count())
                .select_from(SpecialtyMember)
                .where(SpecialtyMember.specialty_id == specialty.id)
            )
            or 0
        )
        return SpecialtyRead(
            id=specialty.id,
            name=specialty.name,
            description=specialty.description,
            active=specialty.active,
            member_count=count,
        )
    return SpecialtyRead(
        id=specialty.id,
        name=specialty.name,
        description=specialty.description,
        active=specialty.active,
        member_count=len(members),
        members=members,
    )


def _require_admin(current: User) -> None:
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("", response_model=SpecialtyRead, status_code=status.HTTP_201_CREATED)
def create_specialty(
    data: SpecialtyCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if db.scalar(select(Specialty).where(Specialty.name == name)):
        raise HTTPException(status_code=400, detail="Specialty already exists")
    specialty = Specialty(
        name=name, description=(data.description or "").strip() or None
    )
    db.add(specialty)
    db.commit()
    db.refresh(specialty)
    return _read(db, specialty, with_members=False)


@router.get("", response_model=list[SpecialtyRead])
def list_specialties(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    specialties = db.scalars(select(Specialty).order_by(Specialty.name)).all()
    return [_read(db, s, with_members=False) for s in specialties]


@router.get("/mine", response_model=list[SpecialtyRead])
def my_specialties(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Specialties the signed-in user belongs to (shown in the user menu)."""
    specialties = db.scalars(
        select(Specialty)
        .join(SpecialtyMember, SpecialtyMember.specialty_id == Specialty.id)
        .where(SpecialtyMember.user_id == current.id, Specialty.active.is_(True))
        .order_by(Specialty.name)
    ).all()
    return [_read(db, s, with_members=False) for s in specialties]


@router.get("/roster", response_model=list[SpecialtyRead])
def roster(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Active specialties with members — one call for the send-review dialog."""
    specialties = db.scalars(
        select(Specialty).where(Specialty.active.is_(True)).order_by(Specialty.name)
    ).all()
    return [_read(db, s, with_members=True) for s in specialties]


@router.get("/{specialty_id}", response_model=SpecialtyRead)
def read_specialty(
    specialty_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    specialty = db.get(Specialty, specialty_id)
    if specialty is None:
        raise HTTPException(status_code=404, detail="Specialty not found")
    return _read(db, specialty, with_members=True)


@router.patch("/{specialty_id}", response_model=SpecialtyRead)
def update_specialty(
    specialty_id: str,
    data: SpecialtyUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    specialty = db.get(Specialty, specialty_id)
    if specialty is None:
        raise HTTPException(status_code=404, detail="Specialty not found")
    patch = data.model_dump(exclude_unset=True)
    if "name" in patch and patch["name"] is not None:
        name = patch["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        clash = db.scalar(select(Specialty).where(Specialty.name == name))
        if clash is not None and clash.id != specialty.id:
            raise HTTPException(status_code=400, detail="Specialty already exists")
        specialty.name = name
    if "description" in patch:
        specialty.description = (patch["description"] or "").strip() or None
    if "active" in patch and patch["active"] is not None:
        specialty.active = patch["active"]
    db.commit()
    db.refresh(specialty)
    return _read(db, specialty, with_members=True)


@router.post("/{specialty_id}/members", response_model=SpecialtyRead)
def add_member(
    specialty_id: str,
    data: MemberAdd,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    specialty = db.get(Specialty, specialty_id)
    if specialty is None:
        raise HTTPException(status_code=404, detail="Specialty not found")
    user = db.get(User, data.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    exists = db.scalar(
        select(SpecialtyMember).where(
            SpecialtyMember.specialty_id == specialty.id,
            SpecialtyMember.user_id == user.id,
        )
    )
    if exists is None:
        db.add(SpecialtyMember(specialty_id=specialty.id, user_id=user.id))
        db.commit()
    return _read(db, specialty, with_members=True)


@router.delete("/{specialty_id}/members/{user_id}", response_model=SpecialtyRead)
def remove_member(
    specialty_id: str,
    user_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    membership = db.scalar(
        select(SpecialtyMember).where(
            SpecialtyMember.specialty_id == specialty_id,
            SpecialtyMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    specialty = db.get(Specialty, specialty_id)
    db.delete(membership)
    db.commit()
    return _read(db, specialty, with_members=True)
