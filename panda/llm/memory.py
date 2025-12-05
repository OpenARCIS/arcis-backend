"""Context memory stub for PANDA."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message structure - aligned with router/models.py ChatMessage."""
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BaseMemory(ABC):
    """Memory contract for context storage."""

    @abstractmethod
    def add(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to memory.
        
        Args:
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata dictionary
        """
        raise NotImplementedError

    @abstractmethod
    def recent(self, limit: int = 10) -> List[ChatMessage]:
        """Get recent messages from memory.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of ChatMessage objects
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored messages."""
        raise NotImplementedError

    @abstractmethod
    def get_context(self, limit: int = 10) -> str:
        """Get formatted context string for LLM prompts.
        
        Args:
            limit: Maximum number of messages to include
            
        Returns:
            Formatted context string
        """
        raise NotImplementedError


class ContextMemory(BaseMemory):
    """In-memory store; swap with DB or vector store later."""

    def __init__(self) -> None:
        self._history: List[ChatMessage] = []

    def add(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to memory."""
        message = ChatMessage(role=role, content=content, metadata=metadata)
        self._history.append(message)

    def recent(self, limit: int = 10) -> List[ChatMessage]:
        """Get recent messages from memory."""
        return self._history[-limit:]

    def clear(self) -> None:
        """Clear all stored messages."""
        self._history.clear()

    def get_context(self, limit: int = 10) -> str:
        """Get formatted context string for LLM prompts."""
        recent_messages = self.recent(limit)
        context_parts = []
        for msg in recent_messages:
            context_parts.append(f"{msg.role}: {msg.content}")
        return "\n".join(context_parts)


__all__ = ["BaseMemory", "ContextMemory", "ChatMessage"]

