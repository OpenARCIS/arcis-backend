from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime, timezone
from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState
from arcis.models.agents.response import PlanModel
from arcis.core.workflow_tg_dm.prompts.tg_dm_analyzer import TG_DM_ANALYZER_PROMPT
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


async def tg_dm_analyzer_node(state: AgentState) -> AgentState:
    """
    Analyzes the input Telegram DM and creates an execution plan.
    """
    dm_content = state["input"]
    
    LOGGER.info("TG_DM_ANALYZER: Analyzing incoming DM...")
    
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", TG_DM_ANALYZER_PROMPT),
        ("human", "Current Date and Time: {current_time}\n\n{input}")
    ])
    
    # Get generic LLM client (can use specific one if configured)
    llm = LLMFactory.get_client_for_agent("planner") # reusing planner config
    structured_llm = llm.with_structured_output(PlanModel, include_raw=True)
    chain = analyzer_prompt | structured_llm
    
    try:
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        response = await chain.ainvoke({"input": dm_content, "current_time": current_time})
        plan_response = response["parsed"]

        # Save token usage
        if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
            await save_token_usage("analyzer", response["raw"].usage_metadata)
        
        if not plan_response.steps:
            LOGGER.info("TG_DM_ANALYZER: Msg ignored due to empty plan (Irrelevant/Unactionable)")
            return {
                **state,
                "plan": [],
                "workflow_status": "FINISHED",
                "final_response": "Could not take any action for this message."
            }
            
        # Convert PlanModel steps to state format
        new_plan = []
        for i, step in enumerate(plan_response.steps):
            new_plan.append({
                "id": i + 1,
                "description": step.description,
                "assigned_agent": step.assigned_agent, # type: ignore
                "status": "pending"
            })
            
        LOGGER.info(f"Plan Created with {len(new_plan)} steps.")
        for step in new_plan:
             LOGGER.info(f"   - {step['id']}: {step['description']} ({step['assigned_agent']})")

        return {
            **state,
            "plan": new_plan,
            "workflow_status": "CONTINUE",
            "current_step_index": 0
        }
        
    except Exception as e:
        LOGGER.error(f"Error in TG DM analysis: {e}")
        return {
            **state,
            "workflow_status": "FAILED",
            "final_response": f"Error analyzing message: {str(e)}"
        }
