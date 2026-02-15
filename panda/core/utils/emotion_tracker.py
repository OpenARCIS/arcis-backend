from datetime import datetime, timezone
from panda.database.mongo.connection import mongo, COLLECTIONS
from panda.models.agents.response import UserEmotion

async def save_user_emotion(emotion: UserEmotion, input_text: str):
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
            print(f"😊 Saved user emotion: {emotion.model_dump()}")
    except Exception as e:
        print(f"⚠️ Failed to save user emotion: {e}")
