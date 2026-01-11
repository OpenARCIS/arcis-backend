from fastapi import APIRouter, HTTPException
from panda.core.llm.config_manager import config_manager
from panda.router.models.settings import SettingsUpdateModel
from panda.core.llm.llm_list import (
    MISTRAL_AI, CEREBRAS, GROQ, 
    OPENAI, GEMINI, ANTHROPIC, OPENROUTER, OLLAMA
)
from panda.models.llm import LLMProvider


settings_router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}},
)


@settings_router.get("/models")
async def get_available_models():
    """
    Get list of available LLM models per provider.
    """
    return {
        LLMProvider.MISTRAL.value: MISTRAL_AI,
        LLMProvider.CEREBRAS.value: CEREBRAS,
        LLMProvider.GROQ.value: GROQ,
        LLMProvider.OPENROUTER.value: OPENROUTER, 
        LLMProvider.OPENAI.value: OPENAI, 
        LLMProvider.GEMINI.value: GEMINI,
        LLMProvider.ANTHROPIC.value: ANTHROPIC,
        LLMProvider.OLLAMA.value: OLLAMA 
    }


@settings_router.get("/agents")
async def get_agent_configs():
    """
    Get current configuration for all agents.
    """
    return config_manager.get_all_configs()

@settings_router.put("/agents")
async def update_agent_configs(settings: SettingsUpdateModel):
    """
    Update configuration for agents.
    """
    try:
        # Convert Pydantic models to dict
        new_config = {}
        for agent_name, agent_config in settings.agent_configs.items():
            new_config[agent_name] = agent_config.model_dump()
            
        await config_manager.update_config(new_config)
        return {"status": "success", "message": "Configuration updated successfully", "config": config_manager.get_all_configs()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")
