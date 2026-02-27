from fastapi import APIRouter, HTTPException

from arcis.router.models.onboarding import (
    OnboardingStartResponse,
    OnboardingRespondRequest,
    OnboardingRespondResponse,
    OnboardingStatusResponse,
)
from arcis.core.onboarding.interviewer import (
    start_interview,
    continue_interview,
    get_onboarding_status,
)


onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@onboarding_router.post("/start", response_model=OnboardingStartResponse)
async def start_onboarding():
    """Start a new onboarding interview session."""
    try:
        result = await start_interview()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@onboarding_router.post("/respond", response_model=OnboardingRespondResponse)
async def respond_onboarding(request: OnboardingRespondRequest):
    """Send user answer and get next question or completion."""
    try:
        result = await continue_interview(request.session_id, request.answer)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@onboarding_router.get("/status", response_model=OnboardingStatusResponse)
async def onboarding_status():
    """Check if user has completed onboarding."""
    try:
        return get_onboarding_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
