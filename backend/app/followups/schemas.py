from datetime import datetime

from pydantic import BaseModel


class FollowUpAsk(BaseModel):
    patient_id: str
    question: str


class FollowUpRead(BaseModel):
    id: str
    patient_id: str
    asked_by: str
    asker_name: str = ""
    question: str
    question_i18n: dict = {}
    answer_text: str = ""
    answer_original: str = ""
    has_audio: bool = False
    status: str
    created_at: datetime
    answered_at: datetime | None = None


class PatientQuestionAnswer(BaseModel):
    answer_text: str
    # Clinician-checked translations, edited before sending. Blank falls
    # back to the English text so the portal always has something to show.
    answer_sw: str = ""
    answer_lg: str = ""


class AnswerTranslation(BaseModel):
    en: str = ""
    sw: str = ""
    lg: str = ""


class PatientQuestionRead(BaseModel):
    id: str
    patient_id: str
    question: str
    question_original: str = ""
    answer_text: str = ""
    answer_i18n: dict = {}
    answerer_name: str = ""
    status: str
    created_at: datetime
    answered_at: datetime | None = None
