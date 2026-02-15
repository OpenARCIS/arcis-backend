from fastapi import APIRouter, HTTPException
from panda.database.mongo.connection import mongo, COLLECTIONS
from panda.models.agents.response import UserEmotion

user_status_router = APIRouter()

@user_status_router.get("/user/status")
async def get_user_status():
    """
    Get the latest user emotion status.
    """
    try:
        if mongo.db is None:
             raise HTTPException(status_code=503, detail="Database not connected")

        # Find the latest emotion record
        cursor = mongo.db[COLLECTIONS['user_emotions']].find().sort("timestamp", -1).limit(1)
        
        latest_emotion = None
        async for document in cursor:
            latest_emotion = document
            break
            
        if not latest_emotion:
            return {"status": "No emotion data available"}

        return latest_emotion.get("emotions", {})

    except Exception as e:
        print(f"Error fetching user status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
