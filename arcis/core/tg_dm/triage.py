from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from arcis.core.llm.factory import LLMFactory
from arcis.logger import LOGGER


TRIAGE_PROMPT = """You are a message classifier for a personal AI assistant.

A message was sent to the assistant's owner by an external contact on Telegram.
Classify this message into exactly one of three categories:

- SOCIAL: Casual conversation, greetings, making plans, asking if someone is free, personal chat.
  Examples: "hey are you free?", "lets grab coffee", "babe, how was your day?"

- ACTIONABLE: The sender is requesting the owner to do something, buy something, schedule something,
  remember something, or take any real-world action.
  Examples: "buy milk when you comeback", "remind me about the meeting tomorrow", "can you book a table?"

- IGNORE: Spam, promotional content, bot messages, irrelevant or automated messages.
  Examples: "You won a prize!", "Click here to claim your offer"

Respond ONLY with a JSON object: {{"type": "SOCIAL"|"ACTIONABLE"|"IGNORE", "reason": "<one sentence>"}}
"""


class TriageResult(BaseModel):
    type: str   # "SOCIAL" | "ACTIONABLE" | "IGNORE"
    reason: str


async def classify_message(text: str, sender_name: str) -> TriageResult:
    """
    Classify an incoming DM as SOCIAL, ACTIONABLE, or IGNORE using a fast LLM.
    Falls back to SOCIAL on any error so the user always gets notified.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", TRIAGE_PROMPT),
        ("human", "Sender: {sender_name}\nMessage: {message}")
    ])

    try:
        llm = LLMFactory.get_client_for_agent("planner")
        structured_llm = llm.with_structured_output(TriageResult)
        chain = prompt | structured_llm

        result: TriageResult = await chain.ainvoke({
            "sender_name": sender_name,
            "message": text
        })

        LOGGER.info(f"Triage [{sender_name}]: {result.type} — {result.reason}")
        return result

    except Exception as e:
        LOGGER.error(f"Triage LLM error: {e}. Defaulting to SOCIAL.")
        return TriageResult(type="SOCIAL", reason="Triage failed, defaulting to safe path.")
