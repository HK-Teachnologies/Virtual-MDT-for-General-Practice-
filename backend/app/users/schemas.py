from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.users.models import USER_ROLES


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: str = "doctor"

    @field_validator("role")
    @classmethod
    def _check_role(cls, value: str) -> str:
        if value not in USER_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(USER_ROLES))}")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str | None = None
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
