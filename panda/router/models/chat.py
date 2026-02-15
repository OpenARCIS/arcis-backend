from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

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