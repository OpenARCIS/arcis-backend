from datetime import datetime, timezone
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER


async def save_token_usage(agent_name: str, usage_metadata: dict, model_name: str = None):
    """
    Extracts token usage from metadata and saves it to MongoDB.
    
    Args:
        agent_name: Name of the agent (e.g., 'planner', 'email_agent')
        usage_metadata: Dictionary containing usage info (usually from LLM response)
                        Expected keys: 'input_tokens', 'output_tokens', 'total_tokens'
                        or 'prompt_tokens', 'completion_tokens', 'total_tokens'
        model_name: Optional name of the model used
    """
    if not usage_metadata:
        return

    # Normalize keys (different providers might use slightly different names)
    prompt_tokens = usage_metadata.get("input_tokens") or usage_metadata.get("prompt_tokens", 0)
    completion_tokens = usage_metadata.get("output_tokens") or usage_metadata.get("completion_tokens", 0)
    total_tokens = usage_metadata.get("total_tokens", prompt_tokens + completion_tokens)

    # don't save empty records
    if total_tokens == 0:
        return

    record = {
        "agent_name": agent_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "timestamp": datetime.now(timezone.utc)
    }

    try:
        if mongo.db is not None:
             await mongo.db[COLLECTIONS['token_usage']].insert_one(record)
    except Exception as e:
        LOGGER.error(f"Failed to save token usage for {agent_name}: {e}")
