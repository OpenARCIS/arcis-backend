from langgraph.graph import StateGraph, END

from panda.models.agents.state import AgentState

from panda.core.workflow_manual.agents.planner import planner_node
from panda.core.workflow_manual.agents.supervisor import supervisor_node, supervisor_router
from panda.core.workflow_manual.agents.email_agent import email_agent_node
from panda.core.workflow_manual.agents.booking_agent import booking_agent_node
from panda.core.workflow_manual.agents.general_agent import general_agent_node
from panda.core.workflow_manual.agents.replanner import replanner_node, replanner_router

from panda.core.llm.short_memory import checkpointer #mongodb per thread memory


def create_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner", planner_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("general_agent", general_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    # planner to supervisor
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "supervisor")
    
    # supervisor has edges to other agents
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
    
    # all agents have a single edge to replanner
    workflow.add_edge("email_agent", "replanner")
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("general_agent", "replanner")
    
    # replanner either ends or continues to supervisor
    workflow.add_conditional_edges(
        "replanner",
        replanner_router,
        {
            "continue": "supervisor",
            "end": END
        }
    )
    
    return workflow


async def run_workflow(user_input: str, thread_id: str | None):
    workflow = create_workflow()
    app = workflow.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    current_state = await app.aget_state(config)

    if not current_state.values:
        payload = {
            "input": user_input,
            "plan": [],
            "current_step_index": 0,
            "context": {},
            "last_tool_output": "", #TODO remove these values by using baseclass in the data model.
            "final_response": "",   # also check if these data are accessed properly using .get()
            "thread_id": thread_id
        }
    else:
        payload = {
            "input": user_input,
            "thread_id": thread_id
        }

    print(f"📝 User Request: {user_input}")
    
    final_state = await app.ainvoke(
        payload,
        {"configurable": {"thread_id": thread_id}}
    )
    
    print(final_state)
    
    return final_state
