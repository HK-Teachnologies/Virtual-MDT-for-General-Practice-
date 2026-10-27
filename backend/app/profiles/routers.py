from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.profiles.models import Profile
from app.profiles.schemas import ProfileRead, ProfileUpdate
from app.users.models import User
from app.users.routers import get_current_user

router = APIRouter()


def get_or_create_profile(db: Session, user_id: str) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/me", response_model=ProfileRead)
def read_own_profile(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return get_or_create_profile(db, current.id)


@router.patch("/me", response_model=ProfileRead)
def update_own_profile(
    data: ProfileUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, current.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
