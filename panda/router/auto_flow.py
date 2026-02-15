from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from panda.core.llm.pending_interrupt import get_all_pending, dismiss_pending
from panda.core.workflow_auto.auto_flow import resolve_interrupt

auto_flow_router = APIRouter()


# --- Models ---

class PendingItemSchema(BaseModel):
    id: str = Field(..., alias="_id")
    thread_id: str
    question: str
    status: str
    source_context: dict = {}
    created_at: float

    class Config:
        populate_by_name = True

class ResolveRequest(BaseModel):
    interrupt_id: str
    answer: str

class DismissRequest(BaseModel):
    interrupt_id: str

class ResolveResponse(BaseModel):
    status: str
    message: str
    workflow_status: Optional[str] = None


# --- Endpoints ---

@auto_flow_router.get("/auto_flow/pending", response_model=List[PendingItemSchema])
async def get_pending_items():
    """List all pending interrupt items for user review."""
    return get_all_pending()


@auto_flow_router.post("/auto_flow/resolve", response_model=ResolveResponse)
async def resolve_pending_item(request: ResolveRequest):
    """Provide an answer to a pending interrupt, resuming the workflow."""
    try:
        result = await resolve_interrupt(request.interrupt_id, request.answer)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@auto_flow_router.post("/auto_flow/dismiss", response_model=ResolveResponse)
async def dismiss_pending_item(request: DismissRequest):
    """Dismiss a pending interrupt (user chooses to skip)."""
    try:
        dismiss_pending(request.interrupt_id)
        return {"status": "dismissed", "message": "Item dismissed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
