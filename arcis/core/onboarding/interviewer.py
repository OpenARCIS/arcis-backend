"""
Onboarding Interviewer — Multi-turn LLM conversation to learn about the user.

Session state is persisted in MongoDB so it survives server restarts.
Once the interview is complete, key facts are extracted and stored in Qdrant.
"""

import json
import uuid
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from arcis.core.llm.factory import LLMFactory
from arcis.core.llm.prompts import INTERVIEWER_PROMPT, MEMORY_EXTRACTOR_PROMPT
from arcis.core.llm.long_memory import long_memory
from arcis.core.llm.short_memory import db_client

logger = logging.getLogger(__name__)

# MongoDB collection for onboarding sessions
_db = db_client["arcis_short_memory"]
_sessions_col = _db["onboarding_sessions"]


def _get_session(session_id: str) -> dict | None:
    return _sessions_col.find_one({"session_id": session_id})


def _save_session(session: dict):
    _sessions_col.update_one(
        {"session_id": session["session_id"]},
        {"$set": session},
        upsert=True,
    )


async def start_interview() -> dict:
    """
    Begin a new onboarding interview.

    Returns:
        dict with session_id, question, is_complete
    """
    session_id = str(uuid.uuid4())

    # Get first question from the LLM
    llm = LLMFactory.get_client_for_agent("interviewer")
    messages = [
        SystemMessage(content=INTERVIEWER_PROMPT),
        HumanMessage(content="Hi! I'm new here. Let's get started."),
    ]

    response = await llm.ainvoke(messages)
    first_question = response.content

    # Persist session
    session = {
        "session_id": session_id,
        "status": "in_progress",
        "messages": [
            {"role": "system", "content": INTERVIEWER_PROMPT},
            {"role": "human", "content": "Hi! I'm new here. Let's get started."},
            {"role": "ai", "content": first_question},
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_session(session)

    return {
        "session_id": session_id,
        "question": first_question,
        "is_complete": False,
    }


async def continue_interview(session_id: str, user_answer: str) -> dict:
    """
    Send the user's answer and get the next question (or completion).

    Returns:
        dict with question (or summary), is_complete, and optionally extracted_facts
    """
    session = _get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    if session["status"] != "in_progress":
        raise ValueError(f"Session {session_id} is already {session['status']}")

    # Rebuild LangChain messages from stored history
    lc_messages = []
    for msg in session["messages"]:
        if msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "human":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "ai":
            lc_messages.append(AIMessage(content=msg["content"]))

    # Add the user's new answer
    lc_messages.append(HumanMessage(content=user_answer))

    # Get LLM response
    llm = LLMFactory.get_client_for_agent("interviewer")
    response = await llm.ainvoke(lc_messages)
    ai_reply = response.content

    # Update stored messages
    session["messages"].append({"role": "human", "content": user_answer})
    session["messages"].append({"role": "ai", "content": ai_reply})
    session["updated_at"] = datetime.now().isoformat()

    # Check if interview is done
    is_complete = "[DONE]" in ai_reply
    extracted_facts = []

    if is_complete:
        session["status"] = "completed"
        # Extract and store facts from the full conversation
        extracted_facts = await _extract_and_store_facts(session["messages"])
        clean_reply = ai_reply.replace("[DONE]", "").strip()
    else:
        clean_reply = ai_reply

    _save_session(session)

    result = {
        "question": clean_reply,
        "is_complete": is_complete,
    }
    if is_complete:
        result["extracted_facts"] = extracted_facts
    return result


def get_onboarding_status() -> dict:
    """Check if the user has completed onboarding."""
    completed = _sessions_col.find_one({"status": "completed"})
    if completed:
        return {
            "onboarded": True,
            "completed_at": completed.get("updated_at", ""),
            "session_id": completed["session_id"],
        }
    
    in_progress = _sessions_col.find_one({"status": "in_progress"})
    if in_progress:
        return {
            "onboarded": False,
            "in_progress": True,
            "session_id": in_progress["session_id"],
        }
    
    return {"onboarded": False, "in_progress": False}


async def _extract_and_store_facts(messages: list[dict]) -> list[dict]:
    """
    Use the LLM to distill the interview conversation into key facts,
    then store them in Qdrant as user_profile memories.
    """
    # Format conversation for the extraction LLM
    conversation_lines = []
    for msg in messages:
        if msg["role"] == "human":
            conversation_lines.append(f"User: {msg['content']}")
        elif msg["role"] == "ai":
            conversation_lines.append(f"Interviewer: {msg['content']}")
    conversation_text = "\n".join(conversation_lines)

    llm = LLMFactory.get_client_for_agent("memory_extractor")

    prompt_messages = [
        SystemMessage(content=MEMORY_EXTRACTOR_PROMPT),
        HumanMessage(content=conversation_text),
    ]

    try:
        response = await llm.ainvoke(prompt_messages)
        facts = _parse_facts(response.content)
    except Exception as e:
        logger.error(f"Failed to extract facts from interview: {e}")
        return []

    if not facts:
        return []

    # Force category to user_profile for onboarding facts
    items = [
        {
            "text": fact["text"],
            "category": fact.get("category", "user_profile"),
            "source": "onboarding_interview",
        }
        for fact in facts
    ]

    try:
        long_memory.store_many(items)
        logger.info(f"Stored {len(items)} onboarding facts in long-term memory")
    except Exception as e:
        logger.error(f"Failed to store onboarding facts: {e}")

    return facts


def _parse_facts(raw: str) -> list[dict]:
    """Parse JSON facts from the LLM response."""
    try:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        if isinstance(data, dict) and "facts" in data:
            data = data["facts"]
        if not isinstance(data, list):
            return []

        return [
            {"text": item["text"], "category": item.get("category", "user_profile")}
            for item in data
            if isinstance(item, dict) and "text" in item
        ]
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Failed to parse interview facts: {e}")
        return []
