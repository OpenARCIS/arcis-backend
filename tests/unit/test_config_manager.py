"""
Unit tests for ConfigManager (core/llm/config_manager.py)

Run:  pytest tests/unit/test_config_manager.py -v
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from arcis.core.llm.config_manager import ConfigManager, DEFAULT_AGENTS_CONFIG
from arcis.models.llm import LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_config_manager() -> ConfigManager:
    """
    Return a fresh ConfigManager each time by bypassing the singleton.
    We reset _instance so each test gets a clean object.
    """
    ConfigManager._instance = None
    return ConfigManager()


# ---------------------------------------------------------------------------
# UT-CM-01  Default config loaded when MongoDB is unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_default_config_when_mongo_unavailable():
    """When mongo.client is None, ConfigManager must use built-in defaults."""
    cm = fresh_config_manager()

    fake_mongo = MagicMock()
    fake_mongo.client = None  # simulate "not connected"

    with patch("arcis.core.llm.config_manager.mongo", fake_mongo):
        await cm.load_config()

    # Should fall back to defaults - check a known agent
    config = cm.get_candidate_config("planner")
    default = DEFAULT_AGENTS_CONFIG["planner"]

    assert config["model_name"] == default["model_name"]
    assert config["temperature"] == default["temperature"]


# ---------------------------------------------------------------------------
# UT-CM-02  Database config overrides defaults
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_db_config_overrides_defaults():
    """When MongoDB returns a config document, it should override the default."""
    cm = fresh_config_manager()

    db_override = {
        "planner": {
            "provider": LLMProvider.GEMINI,
            "model_name": "gemini-2.0-flash",
            "temperature": 0.9,
        }
    }

    fake_collection = MagicMock()
    fake_collection.find_one = AsyncMock(
        return_value={"name": "agent_configurations", "config": db_override}
    )
    fake_db = MagicMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_collection)

    fake_mongo = MagicMock()
    fake_mongo.client = MagicMock()  # simulate "connected"
    fake_mongo.db = fake_db

    with patch("arcis.core.llm.config_manager.mongo", fake_mongo):
        await cm.load_config()

    config = cm.get_candidate_config("planner")
    assert config["model_name"] == "gemini-2.0-flash"
    assert config["temperature"] == 0.9


# ---------------------------------------------------------------------------
# UT-CM-03  update_config() persists to MongoDB
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_config_persists_to_mongo():
    """update_config() should call MongoDB update_one with the new config."""
    cm = fresh_config_manager()

    mock_update = AsyncMock()
    fake_collection = MagicMock()
    fake_collection.update_one = mock_update

    fake_db = MagicMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_collection)

    fake_mongo = MagicMock()
    fake_mongo.client = MagicMock()
    fake_mongo.db = fake_db

    new_config = {
        "planner": {
            "provider": LLMProvider.GROQ,
            "model_name": "llama-3.1-8b-instant",
            "temperature": 0.3,
        }
    }

    with patch("arcis.core.llm.config_manager.mongo", fake_mongo):
        await cm.update_config(new_config)

    assert mock_update.called, "update_one should have been called on MongoDB"
    call_args = mock_update.call_args
    # The second argument contains $set with the new config
    assert "$set" in call_args.args[1] or "$set" in call_args.kwargs.get("update", {})


# ---------------------------------------------------------------------------
# UT-CM-04  Unknown agent returns fallback config
# ---------------------------------------------------------------------------
def test_unknown_agent_returns_fallback():
    """Requesting a non-existent agent returns a safe default, never raises."""
    cm = fresh_config_manager()
    config = cm.get_candidate_config("nonexistent_agent_xyz")

    assert "provider" in config
    assert "model_name" in config
    assert "temperature" in config


# ---------------------------------------------------------------------------
# UT-CM-05  get_all_configs returns all known agents
# ---------------------------------------------------------------------------
def test_get_all_configs_returns_all_agents():
    cm = fresh_config_manager()
    all_configs = cm.get_all_configs()

    expected_agents = {
        "planner", "supervisor", "replanner",
        "email_agent", "utility_agent", "booking_agent",
        "scheduler_agent", "analyzer", "memory_extractor", "interviewer",
    }
    for agent in expected_agents:
        assert agent in all_configs, f"Agent '{agent}' missing from all_configs"
