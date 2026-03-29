from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from arcis.core.recommendations.engine import DEFAULT_USER_ID, generate_recommendations
from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.logger import LOGGER


dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# --- Response model ---

class RecommendationCard(BaseModel):
    id: str
    title: str
    body: str
    category: str
    priority: int
    icon: str
    generated_at: Optional[datetime] = None
    user_id: Optional[str] = None

    class Config:
        populate_by_name = True


# --- Helper ---

def _collection():
    return mongo.db[COLLECTIONS["recommendations"]]


# --- Routes ---

@dashboard_router.get("/recommendations", response_model=List[RecommendationCard])
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=20, description="Max number of cards to return"),
):
    """
    Return the current pre-computed recommendations for the dashboard.

    This is a pure read endpoint — no LLM is invoked.
    Results are ordered by priority (highest first), then by generation time.
    The recommendation engine writes to this collection autonomously on a schedule.
    """
    try:
        cursor = (
            _collection()
            .find({"user_id": DEFAULT_USER_ID}, {"_meta": 0})  # exclude internal metadata
            .sort([("priority", -1), ("generated_at", -1)])
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)

        for doc in docs:
            doc["id"] = str(doc.pop("_id"))

        return docs

    except Exception as exc:
        LOGGER.error(f"DASHBOARD: Failed to fetch recommendations: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recommendations")


@dashboard_router.post("/recommendations/refresh", status_code=202)
async def refresh_recommendations():
    """
    Trigger an on-demand recommendation generation cycle.
    Returns 202 Accepted immediately — generation runs in the background.

    Useful for manual refresh buttons on the dashboard.
    """
    import asyncio

    try:
        asyncio.create_task(generate_recommendations())
        return {"status": "accepted", "message": "Recommendation generation started"}
    except Exception as exc:
        LOGGER.error(f"DASHBOARD: Failed to trigger refresh: {exc}")
        raise HTTPException(status_code=500, detail="Failed to trigger recommendation refresh")
