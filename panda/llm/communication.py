"""Communication layer to interface with UI/API and external systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseCommunicationManager(ABC):
    """Communication contract for input/output normalization."""

    @abstractmethod
    def normalize_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate input payload.
        
        Args:
            payload: Raw input payload from API/UI
            
        Returns:
            Normalized payload dictionary
        """
        raise NotImplementedError

    @abstractmethod
    def format_output(self, result: Any) -> Dict[str, Any]:
        """Format output for API response.
        
        Args:
            result: Result data to format
            
        Returns:
            Formatted output dictionary
        """
        raise NotImplementedError


class CommunicationManager(BaseCommunicationManager):
    """Validates and normalizes inbound/outbound messages.
    
    This manager handles:
    - Input validation and normalization
    - Output formatting for API responses
    - Schema validation (to be implemented)
    """

    def normalize_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate input payload.
        
        Supports both direct input and GoalRequest-like structures from router/models.py.
        
        Args:
            payload: Raw input payload
            
        Returns:
            Normalized payload with 'input' and optional 'constraints' keys
        """
        normalized: Dict[str, Any] = {}
        
        # Handle GoalRequest-like structure (from router/models.py)
        if "objective" in payload:
            normalized["input"] = payload["objective"]
            normalized["constraints"] = payload.get("constraints")
        # Handle direct input
        elif "input" in payload:
            normalized["input"] = payload["input"]
            normalized["constraints"] = payload.get("constraints")
        # Handle encrypted input
        elif "encrypted_input" in payload:
            normalized["encrypted_input"] = payload["encrypted_input"]
            normalized["constraints"] = payload.get("constraints")
        else:
            # Fallback: treat entire payload as input
            normalized["input"] = str(payload)
        
        # Preserve other fields
        for key in ["encrypted_input", "metadata", "user_id"]:
            if key in payload:
                normalized[key] = payload[key]
        
        # TODO: Add schema validation using Pydantic models
        # TODO: Add role-based access checks
        
        return normalized

    def format_output(self, result: Any) -> Dict[str, Any]:
        """Format output for API response.
        
        Args:
            result: Result data (dict, string, or other)
            
        Returns:
            Formatted output dictionary
        """
        if isinstance(result, dict):
            return {"result": result, "status": "success"}
        return {"result": result, "status": "success"}


__all__ = ["BaseCommunicationManager", "CommunicationManager"]

