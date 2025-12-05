"""Planner component for breaking tasks into structured plans."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

if TYPE_CHECKING:
    from .core import LLMEngine
    from .memory import BaseMemory


class PlanStep(BaseModel):
    """A single step in a generated plan - aligned with router/models.py SubTask."""
    step_number: int = Field(..., description="Sequential step number")
    description: str = Field(..., description="What needs to be done")
    tool_required: Optional[str] = Field(None, description="e.g., CalendarAPI, BookingAPI")
    estimated_duration: str = Field(default="N/A", description="Estimated time to complete")
    status: str = Field(default="pending", description="pending, in_progress, completed")
    depends_on: Optional[List[int]] = Field(None, description="Step numbers this step depends on")


class Plan(BaseModel):
    """Internal plan structure for LLM processing."""
    goal: str = Field(..., description="The objective to achieve")
    steps: List[PlanStep] = Field(default_factory=list, description="Ordered list of plan steps")


class BasePlanner(ABC):
    """Planner contract."""

    @abstractmethod
    def create_plan(self, goal: str, constraints: Optional[dict] = None) -> Plan:
        """Create a structured plan from a goal.
        
        Args:
            goal: The objective to achieve
            constraints: Optional constraints (time, budget, preferences)
            
        Returns:
            Plan object with ordered steps
        """
        raise NotImplementedError


class Planner(BasePlanner):
    """Planner that breaks down goals into structured execution plans.
    
    Uses LLM Engine to generate intelligent plans and Memory to consider context.
    """

    def __init__(self, engine=None, memory=None):
        """Initialize planner with optional LLM engine and memory dependencies.
        
        Args:
            engine: LLMEngine instance for generating plans (optional)
            memory: BaseMemory instance for context awareness (optional)
        """
        self._engine = engine
        self._memory = memory

    def create_plan(self, goal: str, constraints: Optional[dict] = None) -> Plan:
        """Create a structured plan from a goal.
        
        Uses LLM engine if available, otherwise falls back to heuristic planning.
        Considers memory context if available.
        """
        # Get context from memory if available
        context = ""
        if self._memory:
            context = self._memory.get_context(limit=5)
        
        # Build planning prompt
        constraints_str = f"\nConstraints: {constraints}" if constraints else ""
        context_str = f"\nPrevious context:\n{context}" if context else ""
        
        planning_prompt = f"""Create a detailed execution plan for the following goal:
Goal: {goal}{constraints_str}{context_str}

Break this down into specific, actionable steps. For each step, provide:
- A clear description
- Required tools or APIs (if any)
- Estimated duration
- Dependencies on other steps (if any)

Format the response as a structured plan."""

        # Use LLM engine if available
        if self._engine:
            try:
                llm_response = self._engine.run(planning_prompt)
                # Parse LLM response into plan steps
                # For now, extract structured data from response
                response_text = str(llm_response.get("response", ""))
                # TODO: Parse structured response into PlanStep objects
                # For now, use heuristic fallback
                steps = self._parse_llm_plan(response_text, goal)
            except Exception:
                # Fallback to heuristic if LLM fails
                steps = self._create_heuristic_plan(goal, constraints)
        else:
            # Fallback to heuristic planning
            steps = self._create_heuristic_plan(goal, constraints)
        
        return Plan(goal=goal, steps=steps)

    def _parse_llm_plan(self, response_text: str, goal: str) -> List[PlanStep]:
        """Parse LLM response into PlanStep objects.
        
        TODO: Implement proper parsing logic based on LLM response format.
        """
        # Placeholder: return heuristic plan for now
        return self._create_heuristic_plan(goal)

    def _create_heuristic_plan(self, goal: str, constraints: Optional[dict] = None) -> List[PlanStep]:
        """Create a heuristic plan as fallback."""
        steps = [
            PlanStep(
                step_number=1,
                description="Clarify goal and constraints",
                tool_required=None,
                estimated_duration="5 minutes",
                status="pending"
            ),
            PlanStep(
                step_number=2,
                description="Gather required data",
                tool_required=None,
                estimated_duration="10 minutes",
                status="pending"
            ),
            PlanStep(
                step_number=3,
                description="Propose solution or action",
                tool_required=None,
                estimated_duration="15 minutes",
                status="pending"
            ),
            PlanStep(
                step_number=4,
                description="Summarize and return result",
                tool_required=None,
                estimated_duration="5 minutes",
                status="pending"
            ),
        ]
        return steps


__all__ = ["BasePlanner", "Planner", "Plan", "PlanStep"]

