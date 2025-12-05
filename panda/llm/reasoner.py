"""Reasoner component to interpret plans and context into prompts/actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import LLMEngine
    from .memory import BaseMemory


class BaseReasoner(ABC):
    """Reasoner contract."""

    @abstractmethod
    def select_action(self, plan_step: str, context: Dict[str, Any] | None = None) -> str:
        """Select an action based on plan step and context.
        
        Args:
            plan_step: Description of the plan step to execute
            context: Additional context (goal, history, step details, etc.)
            
        Returns:
            Formatted prompt/action string for LLM execution
        """
        raise NotImplementedError


class Reasoner(BaseReasoner):
    """Reasoner that uses LLM Engine and Memory for intelligent action selection.
    
    Interprets plan steps in context of goal, history, and constraints to generate
    appropriate prompts for LLM execution.
    """

    def __init__(self, engine=None, memory=None):
        """Initialize reasoner with optional LLM engine and memory dependencies.
        
        Args:
            engine: LLMEngine instance for reasoning (optional)
            memory: BaseMemory instance for context (optional)
        """
        self._engine = engine
        self._memory = memory

    def select_action(self, plan_step: str, context: Dict[str, Any] | None = None) -> str:
        """Select an action based on plan step and context.
        
        Uses LLM engine for intelligent reasoning if available, otherwise uses
        rule-based approach. Leverages memory for context awareness.
        """
        context = context or {}
        goal = context.get("goal", "")
        history = context.get("history", "")
        step_details = context.get("step", {})
        
        # Get additional context from memory if available
        if self._memory and not history:
            history = self._memory.get_context(limit=5)
        
        # Build reasoning prompt
        reasoning_prompt = f"""Given the goal: {goal}

Current step to execute: {plan_step}
Step details: {step_details}

Previous conversation context:
{history if history else "No previous context"}

Generate a specific, actionable prompt to execute this step. Consider:
- What information is needed?
- What actions should be taken?
- What tools or APIs might be required?

Provide a clear, executable prompt."""

        # Use LLM engine for reasoning if available
        if self._engine:
            try:
                llm_response = self._engine.run(reasoning_prompt)
                action_prompt = str(llm_response.get("response", ""))
                if action_prompt:
                    return action_prompt
            except Exception:
                # Fallback to rule-based if LLM fails
                pass
        
        # Fallback to rule-based reasoning
        context_note = f"\nGoal: {goal}" if goal else ""
        history_note = f"\nContext: {history}" if history else ""
        return f"Execute: {plan_step}{context_note}{history_note}"


__all__ = ["BaseReasoner", "Reasoner"]

