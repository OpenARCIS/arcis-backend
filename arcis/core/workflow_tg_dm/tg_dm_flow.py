import uuid

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from arcis.models.agents.state import AgentState

from arcis.core.workflow_tg_dm.nodes.tg_dm_analyzer import tg_dm_analyzer_node
from arcis.core.workflow_manual.agents.supervisor import supervisor_node, supervisor_router
from arcis.core.workflow_manual.agents.booking_agent import booking_agent_node
from arcis.core.workflow_manual.agents.utility_agent import utility_agent_node
from arcis.core.workflow_manual.agents.replanner import replanner_node, replanner_router
from arcis.core.workflow_manual.agents.scheduler_agent import scheduler_agent_node

from arcis.core.llm.short_memory import checkpointer
from arcis.logger import LOGGER


def create_tg_dm_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    workflow.add_node("tg_dm_analyzer", tg_dm_analyzer_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("utility_agent", utility_agent_node)
    workflow.add_node("scheduler_agent", scheduler_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    workflow.set_entry_point("tg_dm_analyzer")
    
    def analyzer_router(state: AgentState):
        if state.get("workflow_status") == "FINISHED":
            return END
        return "supervisor"

    workflow.add_conditional_edges(
        "tg_dm_analyzer",
        analyzer_router,
        {
            "supervisor": "supervisor",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "booking_agent": "booking_agent",
            "utility_agent": "utility_agent",
            "scheduler_agent": "scheduler_agent",
            "replanner": "replanner"
        }
    )
    
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("utility_agent", "replanner")
    workflow.add_edge("scheduler_agent", "replanner")
    
    workflow.add_conditional_edges(
        "replanner",
        replanner_router,
        {
            "continue": "supervisor",
            "end": END
        }
    )
    
    return workflow


def _compile_tg_dm_app():
    """Compile the TG DM workflow with checkpointer."""
    workflow = create_tg_dm_workflow()
    return workflow.compile(checkpointer=checkpointer)
