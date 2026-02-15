import uuid
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from panda.core.workflow_manual.manual_flow import run_workflow
from panda.core.llm.chat_history import save_message, get_thread_history, get_all_threads

manual_flow_router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class MessageSchema(BaseModel):
    type: str = Field(..., description="Type of message: 'human', 'ai', 'interrupt'")
    response: str = Field(..., description="The actual text content")
    plan: Optional[List[Dict[str, Any]]] = None
    thread_id: str

class ThreadPreviewSchema(BaseModel):
    thread_id: str
    updated_at: Optional[float] = Field(None, description="Unix timestamp")
    last_message: Optional[str] = None
    last_role: Optional[str] = None


@manual_flow_router.post("/manual_flow/chat", response_model=MessageSchema)
async def chat_manual(request: ChatRequest):
    """
    Trigger the manual workflow with a user message.
    Handles both normal flow and interrupt (human-in-the-loop) responses.
    """
    try:
        thread_id = request.thread_id
        if not thread_id:
            thread_id = str(uuid.uuid4())

        # Save the user's message
        save_message(thread_id, "human", request.message)

        result = await run_workflow(request.message, thread_id)

        # Check if it's an interrupt (agent needs user input)
        if result.get("type") == "interrupt":
            save_message(thread_id, "interrupt", result["response"])
            return {
                "type": "interrupt",
                "response": result["response"],
                "thread_id": thread_id,
            }

        # Normal completion
        ai_response = result.get("final_response", "")
        plan = result.get("plan", [])
        save_message(thread_id, "ai", ai_response, plan)

        return {
            "type": "ai",
            "response": ai_response,
            "plan": plan,
            "thread_id": thread_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@manual_flow_router.get("/manual_flow/all_chats", response_model=List[ThreadPreviewSchema])
async def get_chats():
    """Return all threads for sidebar display."""
    return get_all_threads()


@manual_flow_router.get("/manual_flow/chat/{thread_id}", response_model=List[MessageSchema])
async def get_chat_history_endpoint(thread_id: str):
    """Return full message history for a thread."""
    messages = get_thread_history(thread_id)
    return [
        {
            "type": msg["role"],
            "response": msg["content"],
            "plan": msg.get("plan", []),
            "thread_id": msg["thread_id"],
        }
        for msg in messages
    ]