from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
try:
    from langchain_mistralai import ChatMistralAI
except ImportError:
    ChatMistralAI = None

from panda.models.errors import InvalidAPIKey
from panda.models.llm import LLMProvider
from panda import Config


from panda.core.llm.config_manager import config_manager


class LLMFactory:
    # TODO: Fetch this from database or external config file
    
    @staticmethod
    def get_model_config(agent_name: str) -> dict:
        """
        Get configuration for a specific agent.
        In the future, this can act as a fallback if DB config is missing.
        """
        return config_manager.get_candidate_config(agent_name)

    @staticmethod
    def get_client_for_agent(agent_name: str, **kwargs):
        """
        Factory method to get the correct LLM client for a specific agent based on configuration.
        """
        config = LLMFactory.get_model_config(agent_name)
        
        # Override config with kwargs if provided
        provider = kwargs.pop("provider", config["provider"])
        model_name = kwargs.pop("model_name", config["model_name"])
        temperature = kwargs.pop("temperature", config.get("temperature", 0.7))
        
        return LLMFactory.create_client(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            **kwargs
        )

    @staticmethod
    def create_client(provider: LLMProvider, **kwargs):
        if provider == LLMProvider.GEMINI:
            if not Config.GEMINI_API:
                raise InvalidAPIKey("No valid API Key has been provided to run Gemini")

            return ChatGoogleGenerativeAI(
                model=kwargs.get("model_name", "gemini-1.5-flash"),
                temperature=kwargs.get("temperature", 0.7),
                google_api_key=Config.GEMINI_API,
                max_retries=3,
                timeout=30,
            )

        elif provider == LLMProvider.OPENROUTER:
            if not Config.OPENROUTER_API_KEY:
                raise InvalidAPIKey("No valid API Key has been provided to run OpenRouter")

            return ChatOpenAI(
                model=kwargs.get("model_name", "xiaomi/mimo-v2-flash:free"),
                temperature=kwargs.get("temperature", 0.7),
                api_key=Config.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                max_retries=3,
                timeout=30,
                default_headers={
                    "HTTP-Referer": kwargs.get("referer", "https://test.itsvinayak.eu.org"),
                    "X-Title": kwargs.get("app_name", "Panda"),
                },
            )

        elif provider == LLMProvider.MISTRAL:
            if ChatMistralAI is None:
                raise ImportError("langchain-mistralai is not installed. Please install it to use Mistral provider.")
            
            # Assuming MISTRAL_API_KEY is in Config, or use kwargs/env
            api_key = getattr(Config, "MISTRAL_API_KEY", None) or kwargs.get("api_key")
            if not api_key:
                 # Fallback to check os.environ? For now raise error if not found in Config
                 try:
                     import os
                     api_key = os.environ["MISTRAL_API_KEY"]
                 except KeyError:
                    raise InvalidAPIKey("No valid API Key has been provided to run Mistral")

            return ChatMistralAI(
                model=kwargs.get("model_name", "mistral-small-latest"),
                temperature=kwargs.get("temperature", 0.7),
                mistral_api_key=api_key,
                max_retries=3,
                timeout=30,
            )

        elif provider == LLMProvider.CEREBRAS:
            # Cerebras uses OpenAI SDK
            api_key = getattr(Config, "CEREBRAS_API_KEY", None) or kwargs.get("api_key")
            if not api_key:
                 try:
                     import os
                     api_key = os.environ["CEREBRAS_API_KEY"]
                 except KeyError:
                    raise InvalidAPIKey("No valid API Key has been provided to run Cerebras")
            
            return ChatOpenAI(
                model=kwargs.get("model_name", "llama3.1-8b"),
                temperature=kwargs.get("temperature", 0.7),
                api_key=api_key,
                base_url="https://api.cerebras.ai/v1",
                max_retries=3,
                timeout=30,
            )

        elif provider == LLMProvider.GROQ:
            # Groq uses OpenAI SDK
            api_key = getattr(Config, "GROQ_API_KEY", None) or kwargs.get("api_key")
            if not api_key:
                 try:
                     import os
                     api_key = os.environ["GROQ_API_KEY"]
                 except KeyError:
                    raise InvalidAPIKey("No valid API Key has been provided to run Groq")
            
            return ChatOpenAI(
                model=kwargs.get("model_name", "llama-3.1-8b-instant"),
                temperature=kwargs.get("temperature", 0.7),
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                max_retries=3,
                timeout=30,
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")
