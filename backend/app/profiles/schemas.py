from pydantic import BaseModel, ConfigDict


class ProfileUpdate(BaseModel):
    specialty: str | None = None
    facility: str | None = None
    license_number: str | None = None
    phone: str | None = None
    bio: str | None = None


class ProfileRead(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
