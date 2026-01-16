from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.models.agents.response import ReplannerResponse
from panda.core.llm.prompts import REPLANNER_PROMPT


async def replanner_node(state: AgentState) -> AgentState:
    """Update state based on execution results and determine next steps."""
    
    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )
    
    replanner_prompt = ChatPromptTemplate.from_messages([
        ("system", REPLANNER_PROMPT),
        ("human", """Execution Report:

Current Step: {current_step}
Tool Output: {tool_output}

Plan Status:
{plan_summary}

Evaluate the execution and determine next actions.""")
    ])
    
    plan_summary = "\n".join([
        f"{s['id']}. [{s['status']}] {s['description']}"
        for s in state["plan"]
    ])
    
    llm_client = LLMFactory.get_client_for_agent("replanner")
    replanner_llm = llm_client.with_structured_output(ReplannerResponse)
    
    messages = replanner_prompt.format_messages(
        current_step=str(current_step) if current_step else "None",
        tool_output=state.get("last_tool_output", "No output"),
        plan_summary=plan_summary
    )
    
    response = await replanner_llm.ainvoke(messages)
    
    # Update plan
    updated_plan = state["plan"].copy()
    if current_step:
        for step in updated_plan:
            if step["id"] == current_step["id"]:
                step["status"] = response.step_status
    
    # Add new steps if replanning
    if response.new_steps:
        max_id = max(s["id"] for s in updated_plan)
        for idx, new_step in enumerate(response.new_steps):
            updated_plan.append({
                "id": max_id + idx + 1,
                "description": new_step.description,
                "status": "pending",
                "assigned_agent": new_step.assigned_agent
            })
    
    print(f"\n🔄 REPLANNER: Status = {response.status}")
    if current_step:
        print(f"   Step {current_step['id']} marked as: {response.step_status}")
    if response.new_steps:
        print(f"   Added {len(response.new_steps)} new steps")
    print()
    
    return {
        **state,
        "plan": updated_plan,
        "workflow_status": response.status,
        "final_response": response.final_response
    }


def replanner_router(state: AgentState) -> str:
    """Route based on workflow status."""
    status = state.get("workflow_status", "CONTINUE")
    if status == "FINISHED":
        return "end"
    return "continue"