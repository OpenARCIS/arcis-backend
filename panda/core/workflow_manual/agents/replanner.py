from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.models.agents.response import ReplannerResponse
from panda.core.llm.prompts import REPLANNER_PROMPT
from panda.core.utils.token_tracker import save_token_usage


def _format_history(messages: list, max_turns: int = 10) -> str:
    """Format recent messages into a readable conversation string for the prompt."""
    if not messages:
        return "(No prior conversation)"
    
    recent = messages[-max_turns:]
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")
    
    return "\n".join(lines) if lines else "(No prior conversation)"


async def replanner_node(state: AgentState) -> AgentState:
    """Update state based on execution results and determine next steps."""
    
    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )
    
    history = _format_history(state.get("messages", []))
    
    replanner_prompt = ChatPromptTemplate.from_messages([
        ("system", REPLANNER_PROMPT),
        ("human", """Conversation History:
{history}

Execution Report:

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
    replanner_llm = llm_client.with_structured_output(ReplannerResponse, include_raw=True)
    
    messages = replanner_prompt.format_messages(
        history=history,
        current_step=str(current_step) if current_step else "None",
        tool_output=state.get("last_tool_output", "No output"),
        plan_summary=plan_summary
    )
    
    response = await replanner_llm.ainvoke(messages)
    
    # Save token usage
    if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
        await save_token_usage("replanner", response["raw"].usage_metadata)
    
    response = response["parsed"]
    
    # Update plan
    updated_plan = state["plan"].copy()
    if current_step:
        for step in updated_plan:
            if step["id"] == current_step["id"]:
                step["status"] = response.step_status
    
    # Add new steps if replanning
    if response.new_steps:
        # Find insertion index (immediately after current step)
        insert_idx = 0
        current_step_id = 0
        if current_step:
            current_step_id = current_step["id"]
            # Find the index of the current step in the list
            for i, s in enumerate(updated_plan):
                if s["id"] == current_step_id:
                    insert_idx = i + 1
                    break
        else:
            # If no current step (e.g. at start), insert at beginning
            insert_idx = 0
            
        # Insert new steps
        for i, new_step_model in enumerate(response.new_steps):
            new_plan_step = {
                "id": 0, # Placeholder, will be re-indexed
                "description": new_step_model.description,
                "status": "pending",
                "assigned_agent": new_step_model.assigned_agent
            }
            updated_plan.insert(insert_idx + i, new_plan_step)
            
        # Re-index all steps to ensure sequence is correct
        for i, step in enumerate(updated_plan):
            step["id"] = i + 1
    
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