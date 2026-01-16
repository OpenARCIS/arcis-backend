from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.core.llm.prompts import SUPERVISOR_PROMPT
from panda.models.agents.state import AgentState
from panda.models.agents.response import SupervisorRouterResponse


async def supervisor_node(state: AgentState) -> AgentState:

    pending_steps = [s for s in state["plan"] if s["status"] == "pending"]
    
    if not pending_steps:
        print("\n🎯 SUPERVISOR: No pending steps, routing to replanner\n")
        return {**state, "next_node": "replanner"}
    
    current_step = pending_steps[0]
    
    supervisor_prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_PROMPT),
        ("human", """Current Plan Status:
{plan_summary}

Current Step to Execute:
ID: {step_id}
Description: {step_description}
Assigned Agent: {step_agent}

Determine the next node to route to.""")
    ])
    
    plan_summary = "\n".join([
        f"{s['id']}. [{s['status']}] {s['description']} ({s['assigned_agent']})"
        for s in state["plan"]
    ])

    llm_client = LLMFactory.get_client_for_agent("supervisor")
    supervisor_llm = llm_client.with_structured_output(SupervisorRouterResponse)
    
    messages = supervisor_prompt.format_messages(
        plan_summary=plan_summary,
        step_id=current_step["id"],
        step_description=current_step["description"],
        step_agent=current_step["assigned_agent"]
    )
    
    routing_response = await supervisor_llm.ainvoke(messages)
    
    print(f"\n🎯 SUPERVISOR: Routing to {routing_response.next_node}")
    print(f"   Reason: {routing_response.reasoning}\n")
    
    # Mark current step as in_progress
    updated_plan = state["plan"].copy()
    for step in updated_plan:
        if step["id"] == current_step["id"]:
            step["status"] = "in_progress"
    
    return {
        **state,
        "plan": updated_plan,
        "next_node": routing_response.next_node
    }


def supervisor_router(state: AgentState) -> str:
    """Route to the appropriate node based on supervisor decision."""
    return state.get("next_node", "replanner")