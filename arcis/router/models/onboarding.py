from pydantic import BaseModel
from typing import Optional


class OnboardingStartResponse(BaseModel):
    session_id: str
    question: str
    is_complete: bool = False


class OnboardingRespondRequest(BaseModel):
    session_id: str
    answer: str


class OnboardingRespondResponse(BaseModel):
    question: str
    is_complete: bool
    extracted_facts: Optional[list] = None


class OnboardingStatusResponse(BaseModel):
    onboarded: bool
    in_progress: Optional[bool] = False
    session_id: Optional[str] = None
    completed_at: Optional[str] = None
