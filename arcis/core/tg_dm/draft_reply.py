from langchain_core.prompts import ChatPromptTemplate
from arcis.core.llm.factory import LLMFactory
from arcis.logger import LOGGER


# ── Social draft reply ────────────────────────────────────────────────────────

SOCIAL_DRAFT_PROMPT = """You are generating a reply on behalf of a person whose AI assistant intercepted an incoming message.

Write a short, natural, human-sounding reply that the owner could send back.
- Match the tone of the incoming message (casual if casual, warm if warm).
- Do NOT mention AI or automation.
- Keep it brief — 1-3 sentences max.
- Reply in the same language as the incoming message.
"""


async def generate_draft_reply(message: str, sender_name: str) -> str:
    """
    Generate a short, natural draft reply for a SOCIAL message.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", SOCIAL_DRAFT_PROMPT),
        ("human", "Message from {sender_name}: {message}\n\nWrite the reply:")
    ])

    try:
        llm = LLMFactory.get_client_for_agent("planner")
        chain = prompt | llm
        result = await chain.ainvoke({"sender_name": sender_name, "message": message})
        draft = result.content.strip()
        LOGGER.info(f"Draft reply generated for [{sender_name}]: {draft[:80]}...")
        return draft
    except Exception as e:
        LOGGER.error(f"Draft reply LLM error: {e}")
        return "Hey! Got your message — will get back to you soon 👋"


# ── Actionable acknowledgment ─────────────────────────────────────────────────

ACK_PROMPT = """You are generating a brief acknowledgment message on behalf of a person.
Their AI assistant just handled an incoming request from a contact.

Write a short, friendly reply (1-2 sentences) to acknowledge the request.
- Sound natural and human, do NOT mention AI or bots.
- Be warm and casual.
- Reply in the same language as the original message.
- Do not over-explain.
"""


async def generate_ack_reply(original_message: str, action_summary: str) -> str:
    """
    Generate a short acknowledgment to send back to the contact after an ACTIONABLE message was handled.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", ACK_PROMPT),
        ("human", "Original message: {message}\nAction taken: {summary}\n\nWrite the acknowledgment:")
    ])

    try:
        llm = LLMFactory.get_client_for_agent("planner")
        chain = prompt | llm
        result = await chain.ainvoke({"message": original_message, "summary": action_summary})
        ack = result.content.strip()
        LOGGER.info(f"Ack reply generated: {ack[:80]}...")
        return ack
    except Exception as e:
        LOGGER.error(f"Ack reply LLM error: {e}")
        return "Got it! I'll take care of that 👍"
