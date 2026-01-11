from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from panda.models.llm import LLMProvider

class AgentConfigModel(BaseModel):
    provider: LLMProvider
    model_name: str
    temperature: float = Field(0.7, ge=0.0, le=1.0)

class SettingsUpdateModel(BaseModel):
    # Map agent name to its config
    agent_configs: Dict[str, AgentConfigModel]
