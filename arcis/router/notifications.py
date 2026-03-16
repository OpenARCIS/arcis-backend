from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.errors import InvalidId

from arcis.database.mongo.connection import mongo, COLLECTIONS

notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ---- Response models ----

class NotificationResponse(BaseModel):
    id: str = Field(..., alias="_id")
    title: str
    message: str
    job_id: Optional[str] = None
    level: str = "info"
    read: bool = False
    created_at: datetime

    class Config:
        populate_by_name = True


class ReadResponse(BaseModel):
    status: str
    count: int = 0


# ---- Helpers ----

def _collection():
    return mongo.db[COLLECTIONS['notifications']]


# ---- Routes ----

@notifications_router.get("", response_model=List[NotificationResponse])
async def list_notifications(unread_only: bool = False, limit: int = 50):
    """List notifications, newest first. Optionally filter to unread only."""
    query = {"read": False} if unread_only else {}
    cursor = _collection().find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


@notifications_router.post("/{notification_id}/read", response_model=ReadResponse)
async def mark_read(notification_id: str):
    """Mark a single notification as read."""
    try:
        oid = ObjectId(notification_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    result = await _collection().update_one({"_id": oid}, {"$set": {"read": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok", "count": result.modified_count}


@notifications_router.post("/read-all", response_model=ReadResponse)
async def mark_all_read():
    """Mark all unread notifications as read."""
    result = await _collection().update_many({"read": False}, {"$set": {"read": True}})
    return {"status": "ok", "count": result.modified_count}
