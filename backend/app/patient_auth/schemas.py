from pydantic import BaseModel


class OtpRequest(BaseModel):
    identifier: str  # patient email address or phone number


class OtpVerify(BaseModel):
    identifier: str
    code: str


class OtpSent(BaseModel):
    sent: bool = True


class PatientToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
