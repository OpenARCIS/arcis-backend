# Example for panda/router/routes.py
from fastapi import APIRouter, Depends, HTTPException
from .models import UserLogin, GoalRequest, ExecutionPlanResponse # Importing from the code above

router = APIRouter()

@router.post("/plan", response_model=ExecutionPlanResponse)
async def create_plan(goal: GoalRequest):
    # [cite_start]Logic to call LLM Orchestrator [cite: 7, 23]
    pass