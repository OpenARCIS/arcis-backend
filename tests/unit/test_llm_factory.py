"""
Unit tests for LLMFactory (core/llm/factory.py)

Run:  pytest tests/unit/test_llm_factory.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from arcis.models.llm import LLMProvider
from arcis.models.errors import InvalidAPIKey
from arcis.core.llm.factory import LLMFactory


# ---------------------------------------------------------------------------
# UT-LF-01  Returns Gemini client for LLMProvider.GEMINI
# ---------------------------------------------------------------------------
def test_create_client_gemini():
    """With a valid GEMINI_API key, factory returns ChatGoogleGenerativeAI."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    with patch("arcis.core.llm.factory.Config") as mock_config:
        mock_config.GEMINI_API = "fake-gemini-key"
        client = LLMFactory.create_client(
            provider=LLMProvider.GEMINI,
            model_name="gemini-1.5-flash",
            temperature=0.7,
        )

    assert isinstance(client, ChatGoogleGenerativeAI)


# ---------------------------------------------------------------------------
# UT-LF-02  Returns ChatOpenAI-compatible client for GROQ
# ---------------------------------------------------------------------------
def test_create_client_groq():
    """With a valid GROQ_API_KEY, factory returns a ChatOpenAI instance."""
    from langchain_openai import ChatOpenAI

    with patch("arcis.core.llm.factory.Config") as mock_config:
        mock_config.GROQ_API_KEY = "fake-groq-key"
        mock_config.GEMINI_API = None
        mock_config.OPENROUTER_API_KEY = None
        client = LLMFactory.create_client(
            provider=LLMProvider.GROQ,
            model_name="llama-3.1-8b-instant",
            temperature=0.5,
        )

    assert isinstance(client, ChatOpenAI)


# ---------------------------------------------------------------------------
# UT-LF-03  Returns ChatMistralAI for MISTRAL_AI
# ---------------------------------------------------------------------------
def test_create_client_mistral():
    """With a valid MISTRAL_API_KEY, factory returns ChatMistralAI instance."""
    from langchain_mistralai import ChatMistralAI

    with patch("arcis.core.llm.factory.Config") as mock_config:
        mock_config.MISTRAL_API_KEY = "fake-mistral-key"
        client = LLMFactory.create_client(
            provider=LLMProvider.MISTRAL_AI,
            model_name="mistral-small-latest",
            temperature=0.3,
        )

    assert isinstance(client, ChatMistralAI)


# ---------------------------------------------------------------------------
# UT-LF-04  Missing API key raises InvalidAPIKey
# ---------------------------------------------------------------------------
def test_create_client_missing_gemini_key_raises():
    """When GEMINI_API is None/empty, InvalidAPIKey must be raised."""
    with patch("arcis.core.llm.factory.Config") as mock_config:
        mock_config.GEMINI_API = None

        with pytest.raises(InvalidAPIKey):
            LLMFactory.create_client(
                provider=LLMProvider.GEMINI,
                model_name="gemini-1.5-flash",
            )


def test_create_client_missing_groq_key_raises(monkeypatch):
    """When GROQ_API_KEY is absent from Config AND env, InvalidAPIKey is raised."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with patch("arcis.core.llm.factory.Config") as mock_config:
        mock_config.GROQ_API_KEY = None

        with pytest.raises(InvalidAPIKey):
            LLMFactory.create_client(
                provider=LLMProvider.GROQ,
                model_name="llama-3.1-8b-instant",
            )


# ---------------------------------------------------------------------------
# UT-LF-05  Unknown provider raises ValueError
# ---------------------------------------------------------------------------
def test_create_client_unknown_provider_raises():
    """Passing an unsupported provider enum value must raise ValueError."""
    # Temporarily add a fake enum value — use a string as the provider
    with pytest.raises((ValueError, AttributeError)):
        LLMFactory.create_client(provider="totally_unknown_provider")


# ---------------------------------------------------------------------------
# UT-LF-06  get_client_for_agent delegates to config_manager
# ---------------------------------------------------------------------------
def test_get_client_for_agent_uses_config_manager():
    """get_client_for_agent should call config_manager and pass values to create_client."""
    fake_config = {
        "provider": LLMProvider.GEMINI,
        "model_name": "gemini-2.0-flash",
        "temperature": 0.5,
    }

    with patch("arcis.core.llm.factory.config_manager") as mock_cm, \
         patch("arcis.core.llm.factory.Config") as mock_config, \
         patch("arcis.core.llm.factory.LLMFactory.create_client") as mock_create:

        mock_cm.get_candidate_config.return_value = fake_config
        mock_config.GEMINI_API = "fake-key"
        mock_create.return_value = MagicMock()

        LLMFactory.get_client_for_agent("planner")

        mock_cm.get_candidate_config.assert_called_once_with("planner")
        mock_create.assert_called_once()
