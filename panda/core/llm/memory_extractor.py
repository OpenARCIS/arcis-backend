from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.core.llm.long_memory import long_memory
from panda.core.llm.prompts import MEMORY_EXTRACTOR_PROMPT
from panda.models.agents.response import MemoryExtractionModel

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
    memory_llm = llm.with_structured_output(MemoryExtractionModel, include_raw=True)
    formatted = prompt.format_messages(conversation=conversation_text)

    try:
        response = await memory_llm.ainvoke(formatted)
        parsed = response["parsed"]
        
        # Save token usage
        if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
            try:
                from panda.core.utils.token_tracker import save_token_usage
                await save_token_usage("memory_extractor", response["raw"].usage_metadata)
            except ImportError:
                pass
                
        if not parsed or not parsed.facts:
            print("No key facts extracted from conversation")
            return []
            
        facts = [{"text": f.text, "category": f.category} for f in parsed.facts]
        
    except Exception as e:
        print(f"Memory extraction failed: {e}")
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

