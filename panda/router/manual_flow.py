from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from panda.core.workflow_manual.manual_flow import run_workflow

manual_flow_router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@manual_flow_router.post("/manual_flow/chat")
async def chat_manual(request: ChatRequest):
    """
    Trigger the manual workflow with a user message.
    """
    try:
        final_state = await run_workflow(request.message)
        return {
            "response": final_state.get("final_response"),
            "plan": final_state.get("plan", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
