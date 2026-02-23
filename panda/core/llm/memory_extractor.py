from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.core.llm.long_memory import long_memory
from panda.core.llm.prompts import MEMORY_EXTRACTOR_PROMPT
from panda.core.utils.token_tracker import save_token_usage

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
        
        if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
            await save_token_usage("memory_extractor", response["raw"].usage_metadata)
        if not parsed or not parsed.facts:
            print("No key facts extracted from conversation")
            return []
            
        facts = [{"text": f.text, "category": f.category} for f in parsed.facts]
        
    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return []

    unique_items = []
    for fact in facts:
        # Check if a very similar fact already exists
        existing = long_memory.search(
            query=fact["text"],
            top_k=1,
            category=fact.get("category"),
            score_threshold=0.85 # high value for very close matches
        )
        
        if not existing:
            unique_items.append({
                "text": fact["text"],
                "category": fact.get("category", "key_detail"),
                "source": source,
            })
        else:
            print(f"Skipping duplicate fact (score {existing[0]['score']:.2f}): {fact['text']}")

    if not unique_items:
        print("No new unique facts to store.")
        return facts

    try:
        long_memory.store_many(unique_items)
        print(f"Extracted and stored {len(unique_items)} new facts from conversation")
    except Exception as e:
        print(f"Failed to store extracted memories: {e}")

    return facts

