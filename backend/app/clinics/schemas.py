from pydantic import BaseModel, ConfigDict


class ClinicCreate(BaseModel):
    name: str
    description: str | None = None


class ClinicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None


class ClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    active: bool
