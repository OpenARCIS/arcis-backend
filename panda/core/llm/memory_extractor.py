import json

from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.core.llm.long_memory import long_memory
from panda.core.llm.prompts import MEMORY_EXTRACTOR_PROMPT

from panda.utils.text import format_messages



async def extract_and_store(messages: list, source: str = "conversation") -> list[dict]:
    """
    Analyze conversation messages and extract key facts worth remembering.

    The LLM distills the conversation into simplified, standalone facts
    and categorises each one. Results are stored into Qdrant.

    Args:
        messages: List of LangChain message objects (HumanMessage, AIMessage, etc.)
        source: Label for where these memories came from.

    Returns:
        List of extracted facts (dicts with text + category).
    """
    if not messages:
        return []

    conversation_text = format_messages(messages)

    prompt = ChatPromptTemplate.from_messages([
        ("system", MEMORY_EXTRACTOR_PROMPT),
        ("human", "{conversation}")
    ])

    llm = LLMFactory.get_client_for_agent("memory_extractor")
    formatted = prompt.format_messages(conversation=conversation_text)

    try:
        response = await llm.ainvoke(formatted)
        facts = _parse_facts(response.content)
    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return []

    if not facts:
        print("No key facts extracted from conversation")
        return []

    # Store in Qdrant
    items = [
        {
            "text": fact["text"],
            "category": fact.get("category", "key_detail"),
            "source": source,
        }
        for fact in facts
    ]

    try:
        long_memory.store_many(items)
        print(f"Extracted and stored {len(items)} facts from conversation")
    except Exception as e:
        print(f"Failed to store extracted memories: {e}")

    return facts


def _parse_facts(raw: str) -> list[dict]:
    """Parse the LLM response into a list of fact dicts."""
    try:
        # Try to extract JSON from the response
        text = raw.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)

        if isinstance(data, dict) and "facts" in data:
            data = data["facts"]

        if not isinstance(data, list):
            return []

        # Validate each fact
        valid = []
        for item in data:
            if isinstance(item, dict) and "text" in item:
                valid.append({
                    "text": item["text"],
                    "category": item.get("category", "key_detail"),
                })
        return valid

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Failed to parse memory extraction response: {e}")
        return []
