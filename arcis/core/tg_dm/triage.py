from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from arcis.core.llm.factory import LLMFactory
from arcis.logger import LOGGER


TRIAGE_PROMPT = """You are a message classifier for a personal AI assistant.

A message was sent to the assistant's owner by an external contact on Telegram.
Classify this message into exactly one of the following categories.

IMPORTANT RULE — Any message that mentions a specific time, date, day, or asks
about availability / schedule / "are you free?" MUST be classified as SCHEDULE,
not SOCIAL, even if the overall tone is casual.

- SCHEDULE: The message mentions or implies a time, date, day, meeting, or asks
  about availability. These need a calendar lookup before the owner can respond.
  Examples: "are you free at 5pm?", "let's meet tomorrow", "are you free?",
  "can we do Saturday?", "what time works for you?", "let's grab coffee at 3",
  "wanna hang out this weekend?"

- SOCIAL: Pure casual conversation with NO time/date/availability component.
  Greetings, personal chat, emotional sharing, or banter.
  Examples: "hey, how's it going?", "babe, how was your day?", "haha that's hilarious",
  "good morning!", "miss you", "check this meme out"

- ACTIONABLE: The sender is requesting the owner to do something concrete —
  buy something, remember something, complete a task, or take a real-world action.
  (If the action involves scheduling/meeting, classify as SCHEDULE instead.)
  Examples: "buy milk on your way home", "remind me about the report",
  "can you send me that file?", "call the dentist"

- IGNORE: Spam, promotional content, bot messages, or irrelevant automated messages.
  Examples: "You won a prize!", "Click here to claim your offer"

Respond ONLY with a JSON object:
{{"type": "SCHEDULE"|"SOCIAL"|"ACTIONABLE"|"IGNORE", "reason": "<one sentence>"}}
"""


class TriageResult(BaseModel):
    type: str   # "SCHEDULE" | "SOCIAL" | "ACTIONABLE" | "IGNORE"
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
