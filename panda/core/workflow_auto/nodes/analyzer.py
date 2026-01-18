from langchain_core.prompts import ChatPromptTemplate
from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.models.agents.response import PlanModel
from panda.core.llm.prompts import AUTO_ANALYZER_PROMPT


async def analyzer_node(state: AgentState) -> AgentState:
    """
    Analyzes the input email/message and creates an execution plan.
    """
    email_content = state["input"]
    
    print("\n" + "="*80)
    print(f"📧 ANALYZER: Analyzing incoming message...")
    # print(f"   Content Preview: {email_content[:100]}...")
    
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", AUTO_ANALYZER_PROMPT),
        ("human", "{input}")
    ])
    
    # Get generic LLM client (can use specific one if configured)
    llm = LLMFactory.get_client_for_agent("planner") # reusing planner config
    structured_llm = llm.with_structured_output(PlanModel)
    chain = analyzer_prompt | structured_llm
    
    try:
        plan_response: PlanModel = await chain.ainvoke({"input": email_content})
        
        if not plan_response.steps:
            print("   🚫 Msg ignored (Irrelevant/Spam)")
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
            
        print(f"   ✅ Plan Created with {len(new_plan)} steps.")
        for step in new_plan:
             print(f"      - {step['id']}: {step['description']} ({step['assigned_agent']})")

        return {
            **state,
            "plan": new_plan,
            "workflow_status": "CONTINUE",
            "current_step_index": 0
        }
        
    except Exception as e:
        print(f"   ❌ Error in analysis: {e}")
        return {
            **state,
            "workflow_status": "FAILED",
            "final_response": f"Error analyzing message: {str(e)}"
        }
