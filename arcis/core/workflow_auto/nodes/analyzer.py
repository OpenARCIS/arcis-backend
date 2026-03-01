from langchain_core.prompts import ChatPromptTemplate
from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState
from arcis.models.agents.response import PlanModel
from arcis.core.llm.prompts import AUTO_ANALYZER_PROMPT
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


async def analyzer_node(state: AgentState) -> AgentState:
    """
    Analyzes the input email/message and creates an execution plan.
    """
    email_content = state["input"]
    
    LOGGER.info("ANALYZER: Analyzing incoming message...")
    # LOGGER.debug(f"   Content Preview: {email_content[:100]}...")
    
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", AUTO_ANALYZER_PROMPT),
        ("human", "{input}")
    ])
    
    # Get generic LLM client (can use specific one if configured)
    llm = LLMFactory.get_client_for_agent("planner") # reusing planner config
    structured_llm = llm.with_structured_output(PlanModel, include_raw=True)
    chain = analyzer_prompt | structured_llm
    
    try:
        response = await chain.ainvoke({"input": email_content})
        plan_response = response["parsed"]

        # Save token usage
        if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
            await save_token_usage("analyzer", response["raw"].usage_metadata)
        
        if not plan_response.steps:
            LOGGER.info("Msg ignored (Irrelevant/Spam)")
            return {
                **state,
                "plan": [],
                "workflow_status": "FINISHED",
                "final_response": "Message ignored (irrelevant)"
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
        LOGGER.error(f"Error in analysis: {e}")
        return {
            **state,
            "workflow_status": "FAILED",
            "final_response": f"Error analyzing message: {str(e)}"
        }
