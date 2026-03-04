from datetime import datetime, timezone
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER


async def save_user_emotion(emotion, input_text: str):
    """
    Saves the user's emotion and input text to MongoDB.
    
    Args:
        emotion: UserEmotion object containing happiness, frustration, urgency, confusion scores.
        input_text: The user's request text.
    """
    if not emotion:
        return

    record = {
        "emotions": emotion.model_dump(),
        "input_text": input_text,
        "timestamp": datetime.now(timezone.utc)
    }

    try:
        if mongo.db is not None:
            await mongo.db[COLLECTIONS['user_emotions']].insert_one(record)
            LOGGER.debug(f"Saved user emotion: {emotion.model_dump()}")
    except Exception as e:
        LOGGER.error(f"Failed to save user emotion: {e}")


async def get_recent_emotions(limit: int = 5) -> list[dict]:
    """
    Fetch the most recent user emotion records from MongoDB.

    Args:
        limit: Number of recent records to return.

    Returns:
        List of dicts, each with 'emotions' (dict of scores) and 'timestamp'.
    """
    try:
        if mongo.db is None:
            return []

        cursor = (
            mongo.db[COLLECTIONS['user_emotions']]
            .find({}, {"_id": 0, "emotions": 1, "timestamp": 1})
            .sort("timestamp", -1)
            .limit(limit)
        )
        records = await cursor.to_list(length=limit)
        return records
    except Exception as e:
        LOGGER.error(f"Failed to fetch recent emotions: {e}")
        return []
