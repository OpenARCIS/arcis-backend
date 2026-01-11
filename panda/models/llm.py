from enum import Enum
from abc import ABC, abstractmethod

from pydantic import BaseModel

class LLMProvider(Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    MISTRAL = "mistral"
    CEREBRAS = "cerebras"
    GROQ = "groq"

class BaseLLMClient(ABC):
    def __init__(self, model_name: str, temperature: float = 0.7):
        self.model_name = model_name
        self.temperature = temperature

    @abstractmethod
    async def generate(self, system_role: str, user_query: str) -> str | BaseModel:
        """
        Generate content with LLM.

        Args:
            system_role: System prompt (str)
            user_query: User prompt (str)
        """
        pass