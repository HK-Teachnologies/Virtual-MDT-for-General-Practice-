from pydantic import BaseModel, ConfigDict


class SpecialtyCreate(BaseModel):
    name: str
    description: str | None = None


class SpecialtyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None


class MemberAdd(BaseModel):
    user_id: str


class SpecialtyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    specialty_id: str
    user_id: str


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    role: str


class SpecialtyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    active: bool
    member_count: int = 0
    members: list[UserRef] = []
