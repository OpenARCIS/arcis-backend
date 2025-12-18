from .providers import GeminiClient
from panda.models.errors import InvalidAPIKey
from panda.models.llm import BaseLLMClient, LLMProvider
from panda import Config

class LLMFactory:
    @staticmethod
    def create_client(provider: LLMProvider, **kwargs) -> BaseLLMClient:
        if provider == LLMProvider.GEMINI:
            if not Config.GEMINI_API:
                raise InvalidAPIKey(f"No valid API Key have been provided to run Gemini")
            return GeminiClient(
                model_name=kwargs.get("model_name", "gemini-1.5-flash"),
                api_key=Config.GEMINI_API,
                temperature=kwargs.get("temperature", 0.7),
                response_schema=kwargs.get("response_schema"),
                mime_type=kwargs.get("response_mime_type"),
            )    
        else:
            raise ValueError(f"Unknown provider: {provider}")