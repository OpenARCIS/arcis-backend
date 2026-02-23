from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class UserEmotion(BaseModel):
    happiness: int = Field(description="1-10 scale (1=Very Unhappy, 10=Very Happy)", ge=1, le=10)
    frustration: int = Field(description="1-10 scale (1=Calm, 10=Very Frustrated)", ge=1, le=10)
    urgency: int = Field(description="1-10 scale (1=Low, 10=High)", ge=1, le=10)
    confusion: int = Field(description="1-10 scale (1=Clear, 10=Very Confused)", ge=1, le=10)


class PlanStepModel(BaseModel):
    """Structured output for individual plan steps"""
    description: str = Field(description="Clear, actionable description of the step")
    assigned_agent: Literal["EmailAgent", "BookingAgent", "GeneralAgent"] = Field(
        description="The agent responsible for this step"
    )


class PlanModel(BaseModel):
    """Structured output for the complete plan"""
    is_conversational: bool = Field(
        default=False,
        description="True if the message is a simple greeting, chitchat, or general conversation that does NOT require any tool/agent actions. False for anything actionable."
    )
    direct_response: Optional[str] = Field(
        default=None,
        description="The direct conversational reply when is_conversational=True. Must be friendly, helpful, and context-aware."
    )
    steps: List[PlanStepModel] = Field(
        default_factory=list,
        description="List of sequential steps to complete the task. Empty when is_conversational=True."
    )
    user_emotion: Optional[UserEmotion] = Field(
        default=None,
        description="Analysis of the user's emotional state (Required for Manual Flow)"
    )


class SupervisorRouterResponse(BaseModel):
    """Supervisor's routing decision"""
    next_node: Literal["email_agent", "booking_agent", "general_agent", "replanner"] = Field(
        description="The next node to execute"
    )
    reasoning: str = Field(description="Why this node was chosen")


class ReplannerResponse(BaseModel):
    """Replanner's state update decision"""
    status: Literal["CONTINUE", "FINISHED", "FAILED"] = Field(
        description="Current workflow status"
    )
    step_status: Literal["completed", "failed", "pending"] = Field(
        description="Status of the current step"
    )
    new_steps: List[PlanStepModel] = Field(
        default_factory=list,
        description="Additional steps if replanning needed"
    )
    final_response: str = Field(
        default="",
        description="Final response if workflow is complete"
    )


class MemoryFactModel(BaseModel):
    """Structured output for a single memory fact"""
    text: str = Field(description="Concrete, factual information. Maximum 1-2 sentences.")
    category: Literal["user_profile", "preference", "key_detail", "learned_fact"] = Field(
        description="Category of the fact"
    )


class MemoryExtractionModel(BaseModel):
    """Structured output for the complete memory distillation"""
    facts: List[MemoryFactModel] = Field(
        default_factory=list,
        description="List of extracted facts from the conversation"
    )
