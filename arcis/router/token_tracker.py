from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from arcis.database.mongo.connection import mongo, COLLECTIONS

token_tracker_router = APIRouter(prefix="/token-tracker", tags=["Token Tracker"])

class TokenUsageRecord(BaseModel):
    agent_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model_name: Optional[str] = None
    timestamp: datetime

class AgentStats(BaseModel):
    agent_name: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    request_count: int

@token_tracker_router.get("/agents", response_model=List[str])
async def get_agents():
    """Get a list of all agents that have recorded usage."""
    if mongo.db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    agents = await mongo.db[COLLECTIONS['token_usage']].distinct("agent_name")
    return agents

@token_tracker_router.get("/cumulative", response_model=List[AgentStats])
async def get_cumulative_stats():
    """Get cumulative token usage statistics for each agent."""
    if mongo.db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    pipeline = [
        {
            "$group": {
                "_id": "$agent_name",
                "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                "total_completion_tokens": {"$sum": "$completion_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "request_count": {"$sum": 1}
            }
        },
        {
            "$project": {
                "_id": 0,
                "agent_name": "$_id",
                "total_prompt_tokens": 1,
                "total_completion_tokens": 1,
                "total_tokens": 1,
                "request_count": 1
            }
        }
    ]

    cursor = mongo.db[COLLECTIONS['token_usage']].aggregate(pipeline)
    results = await cursor.to_list(length=None)
    return results

@token_tracker_router.get("/agent/{agent_name}", response_model=List[TokenUsageRecord])
async def get_agent_history(agent_name: str):
    """Get usage history for a specific agent."""
    if mongo.db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    cursor = mongo.db[COLLECTIONS['token_usage']].find({"agent_name": agent_name}).sort("timestamp", -1)
    results = await cursor.to_list(length=100) # Limit to last 100 for now
    return results
