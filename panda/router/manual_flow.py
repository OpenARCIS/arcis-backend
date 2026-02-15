import uuid
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from panda.core.workflow_manual.manual_flow import run_workflow

manual_flow_router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class MessageSchema(BaseModel):
    type: str = Field(..., description="Type of message: 'human', 'ai', 'tool'")
    response: str = Field(..., description="The actual text content")
    plan: Optional[List[Dict[str, Any]]] = None
    thread_id: str

class ThreadPreviewSchema(BaseModel):
    thread_id: str
    updated_at: Optional[int] = Field(None, description="Step number or timestamp")
    last_message: Optional[MessageSchema] = None

# 3. Schema for the List Response
class ThreadListResponse(BaseModel):
    threads: List[ThreadPreviewSchema]


@manual_flow_router.post("/manual_flow/chat", response_model=MessageSchema)
async def chat_manual(request: ChatRequest):
    """
    Trigger the manual workflow with a user message.
    """
    try:
        thread_id = request.thread_id
        if not thread_id:
            thread_id = str(uuid.uuid4())

        final_state = await run_workflow(request.message, thread_id)
        return {
            "type": "ai",
            "response": final_state.get("final_response"),
            "plan": final_state.get("plan", []),
            "thread_id": final_state.get("thread_id", None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))