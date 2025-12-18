from typing import Literal
from pydantic import BaseModel

from panda.core.llm.factory import LLMFactory, LLMProvider
from panda import Config
from panda.models.agents.state import AgentState

# TODO - genai support pydantic response schema - but dunno about others - if possible refactor this
class SupervisorRouter(BaseModel):
    reasoning: str
    next_step: Literal["Scheduler", "Analyst", "Communications"]


supervisor_llm = LLMFactory.create_client(
    provider=LLMProvider.GEMINI,
    api_key=Config.GEMINI_API,
    model_name="gemini-2.5-flash",
    response_schema=SupervisorRouter,
    response_mime_type='application/json',
)

async def supervisor_node(state: AgentState):
    messages = state['messages']
    last_user_message = messages[-1].content
    
    system_prompt = (
        "You are a Supervisor for an AI Agent system. "
        "Your sole job is to route the user query to one of these three workers:\n"
        "1. 'Scheduler' - For calendar events, meetings, and availability.\n"
        "2. 'Analyst' - For sentiment analysis, behavior tracking, and work density checks.\n"
        "3. 'Communications' - For drafting emails, sending WhatsApps, or general chat.\n\n"
    )

    decision = await supervisor_llm.generate(system_prompt, last_user_message)
    
    return {"next_step": decision.next_step}