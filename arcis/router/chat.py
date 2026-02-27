import uuid

from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from .models.chat import *
from arcis.core.workflow_manual.manual_flow import run_workflow
from arcis.core.llm.chat_history import save_message, get_thread_history, get_all_threads
from arcis.core.tts.tts_manager import tts_manager

chat_router = APIRouter(prefix="/chat")

@chat_router.post("/voice-upload")
async def upload_voice(voice_id: str, file: UploadFile = File(...)):
    """Upload a custom voice WAV file and set it as the active voice state."""
    if not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only .wav files are supported")
    
    try:
        content = await file.read()
        success = tts_manager.update_voice_state_from_bytes(voice_id, content)
        if success:
            return {"status": "success", "message": f"Voice '{voice_id}' updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to parse voice state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@chat_router.post("/stream")
async def chat_manual_stream(request: ChatRequest, voice_id: str = "default"):
    """
    Trigger the manual workflow with a user message and stream TTS audio sentence by sentence.
    """
    try:
        thread_id = request.thread_id
        if not thread_id:
            thread_id = str(uuid.uuid4())

        save_message(thread_id, "human", request.message)

        # 1. Run the workflow completely to get the final text response
        result = await run_workflow(request.message, thread_id)

        # Check if it's an interrupt (agent needs user input)
        if result.get("type") == "interrupt":
            save_message(thread_id, "interrupt", result["response"])
            # Even for an interrupt we can play the text response, but we might just want to stream it normally
            import json
            async def interrupt_stream():
                yield f"data: {json.dumps({'type': 'interrupt', 'response': result['response'], 'thread_id': thread_id})}\n\n"
            return StreamingResponse(interrupt_stream(), media_type="text/event-stream")

        # 2. Normal completion
        ai_response = result.get("final_response", "")
        plan = result.get("plan", [])
        save_message(thread_id, "ai", ai_response, plan)
        
        # 3. Stream back the audio
        return StreamingResponse(
            tts_manager.stream_text_and_audio(ai_response, voice_id=voice_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@chat_router.post("", response_model=MessageSchema)
async def chat_manual(request: ChatRequest):
    """
    Trigger the manual workflow with a user message.
    Handles both normal flow and interrupt (human-in-the-loop) responses.
    """
    try:
        thread_id = request.thread_id
        if not thread_id:
            thread_id = str(uuid.uuid4())

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


@chat_router.get("/all_chats", response_model=List[ThreadPreviewSchema])
async def get_chats():
    """Return all threads for sidebar display."""
    return get_all_threads()


@chat_router.get("/{thread_id}", response_model=List[MessageSchema])
async def get_chat_history(thread_id: str):
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