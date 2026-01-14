from langgraph.graph import StateGraph, END

from panda.models.agents.state import AgentState
from panda.core.workflow.agents.planner import planner_node
from panda.core.workflow.agents.supervisor import supervisor_node, supervisor_router
from panda.core.workflow.agents.email_agent import email_agent_node
from panda.core.workflow.agents.booking_agent import booking_agent_node
from panda.core.workflow.agents.general_agent import general_agent_node
from panda.core.workflow.agents.replanner import replanner_node, replanner_router


def create_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("general_agent", general_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    # Define edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "supervisor")
    
    # Conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "email_agent": "email_agent",
            "booking_agent": "booking_agent",
            "general_agent": "general_agent",
            "replanner": "replanner"
        }
    )
    
    # All workers route to replanner
    workflow.add_edge("email_agent", "replanner")
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("general_agent", "replanner")
    
    # Conditional routing from replanner
    workflow.add_conditional_edges(
        "replanner",
        replanner_router,
        {
            "continue": "supervisor",
            "end": END
        }
    )
    
    return workflow


def run_workflow(user_input: str):
    """Execute the workflow with a user request."""
    
    # Create and compile workflow
    workflow = create_workflow()
    app = workflow.compile()
    
    # Initialize state
    initial_state: AgentState = {
        "input": user_input,
        "plan": [],
        "context": {},
        "last_tool_output": "",
        "final_response": "",
        "current_step_index": 0
    }
    
    print("\n" + "="*80)
    print(f"🚀 STARTING WORKFLOW")
    print(f"📝 User Request: {user_input}")
    print("="*80)
    
    # Execute workflow
    final_state = app.invoke(initial_state)
    
    print("\n" + "="*80)
    print("✅ WORKFLOW COMPLETED")
    print(f"📊 Plan Execution Summary:")
    for step in final_state["plan"]:
        status_emoji = {"completed": "✅", "failed": "❌", "pending": "⏳"}
        emoji = status_emoji.get(step["status"], "❓")
        print(f"  {emoji} Step {step['id']}: {step['description']} [{step['status']}]")
    print(f"\n💬 Final Response: {final_state.get('final_response', 'No response generated')}")
    print("="*80 + "\n")
    
    return final_state
