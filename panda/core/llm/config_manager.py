from typing import Dict, Any, Optional
import asyncio
import logging

from panda.models.llm import LLMProvider
from panda.database.mongo.connection import mongo

logger = logging.getLogger(__name__)

DEFAULT_AGENTS_CONFIG = {
    "supervisor": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    },
    "email_agent": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    },
    "scheduler_agent": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    },
    "booking_agent": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    },
    "chitchat_agent": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    },
    "health_monitor": {
        "provider": LLMProvider.OPENROUTER,
        "model_name": "mistralai/devstral-2512:free",
        "temperature": 0.7
    }
}

class ConfigManager:
    """
    Manages loading and updating of agent configurations.
    Prioritizes configuration from the database, falling back to defaults.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.config: Dict[str, Any] = DEFAULT_AGENTS_CONFIG.copy()
        self._initialized = True
        self._db_collection_name = 'settings'
        self._config_doc_name = "agent_configurations"

    async def load_config(self):
        """
        Loads the configuration from the database.
        Updates local config with values from the database.
        """
        try:
            # dependent on mongo connection being established
            if not mongo.client:
                logger.warning("MongoDB client not connected. Using default config.")
                return

            doc = await mongo.db[self._db_collection_name].find_one(
                {"name": self._config_doc_name}
            )
            
            if doc and "config" in doc:
                logger.info("Loaded agent configurations from database.")
                # Merge DB config into current config (to preserve defaults for missing keys if any)
                # Or simply replace. Here we replace keys present in DB.
                db_config = doc["config"]
                for agent, settings in db_config.items():
                    self.config[agent] = settings
            else:
                logger.info("No agent configurations found in database. Using defaults.")
                # Optionally seed the DB with defaults?
                # await self.update_config(self.config) 

        except Exception as e:
            logger.error(f"Failed to load config from database: {e}. Using defaults.")

    def get_candidate_config(self, agent_name: str) -> Dict[str, Any]:
        """
        Retrieves the configuration for a specific agent.
        """
        # Return default structure if agent not found, though ideally all agents are in config
        return self.config.get(agent_name, {
            "provider": LLMProvider.OPENROUTER,
            "model_name": "mistralai/devstral-2512:free",
            "temperature": 0.7
        })

    def get_all_configs(self) -> Dict[str, Any]:
        return self.config

    async def update_config(self, new_config: Dict[str, Any]):
        """
        Updates the configuration in memory and persists it to the database.
        """
        try:
            # Validate or sanitize new_config here if necessary
            self.config.update(new_config)
            
            if not mongo.client:
                logger.warning("MongoDB client not connected. Config updated in memory only.")
                return

            await mongo.db[self._db_collection_name].update_one(
                {"name": self._config_doc_name},
                {"$set": {"config": self.config}},
                upsert=True
            )
            logger.info("Agent configurations updated in database.")
            
        except Exception as e:
            logger.error(f"Failed to update config in database: {e}")
            raise e

# Global instance
config_manager = ConfigManager()
