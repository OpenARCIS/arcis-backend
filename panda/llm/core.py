"""LLM integration stubs (Gemini placeholder)."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import BaseMemory


class BaseLLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Return a completion for the prompt."""
        raise NotImplementedError


class GeminiClient(BaseLLMClient):
    """Lightweight wrapper for a Gemini-style LLM API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro") -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY or pass api_key.")

    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Generate a completion for the given prompt.

        This is a placeholder; replace with real HTTP call to Gemini endpoint.
        """
        # TODO: Implement API request to Gemini service and handle errors.
        return {
            "model": self.model,
            "prompt": prompt,
            "kwargs": kwargs,
            "response": "This is a stub response from GeminiClient.",
        }


class LLMEngine:
    """Thin engine abstraction to swap LLM providers without changing orchestration.
    
    Can be enhanced with memory context for better prompt construction.
    """

    def __init__(self, client: Optional[BaseLLMClient] = None, memory=None) -> None:
        """Initialize LLM engine with optional client and memory.
        
        Args:
            client: LLM client implementation (defaults to GeminiClient)
            memory: BaseMemory instance for context injection (optional)
        """
        self.client = client or GeminiClient()
        self._memory = memory

    def run(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Run LLM generation with optional context from memory.
        
        Args:
            prompt: The prompt to send to LLM
            **kwargs: Additional parameters for LLM generation
            
        Returns:
            Dictionary with LLM response
        """
        # Enhance prompt with memory context if available
        enhanced_prompt = self._enhance_prompt(prompt)
        
        # Add memory context to kwargs if not already present
        if self._memory and "context" not in kwargs:
            context = self._memory.get_context(limit=5)
            if context:
                kwargs["context"] = context
        
        return self.client.generate(enhanced_prompt, **kwargs)

    def _enhance_prompt(self, prompt: str) -> str:
        """Enhance prompt with memory context if available.
        
        Args:
            prompt: Original prompt
            
        Returns:
            Enhanced prompt with context
        """
        if self._memory:
            context = self._memory.get_context(limit=5)
            if context:
                return f"Context from previous conversation:\n{context}\n\n{prompt}"
        return prompt


__all__ = ["BaseLLMClient", "GeminiClient", "LLMEngine"]

