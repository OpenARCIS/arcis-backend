from typing import TypedDict, List, Dict, Any, Literal, Optional


class PlanStep(TypedDict):
    id: int
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    assigned_agent: Literal["EmailAgent", "BookingAgent", "GeneralAgent"]


class AgentState(TypedDict):
    input: str  # Original user request
    plan: List[PlanStep]  # Breakdown of tasks
    context: Dict[str, Any]  # Accumulated context
    last_tool_output: str  # Output from last worker
    final_response: str  # Final answer for user
    current_step_index: int  # Track which step we're on
    next_node: Optional[Literal["email_agent", "booking_agent", "general_agent", "replanner"]]
    workflow_status: Optional[Literal["CONTINUE", "FINISHED", "FAILED"]]