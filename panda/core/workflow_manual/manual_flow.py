from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage

from panda.models.agents.state import AgentState

from panda.core.workflow_manual.agents.planner import planner_node
from panda.core.workflow_manual.agents.supervisor import supervisor_node, supervisor_router
from panda.core.workflow_manual.agents.email_agent import email_agent_node
from panda.core.workflow_manual.agents.booking_agent import booking_agent_node
from panda.core.workflow_manual.agents.utility_agent import utility_agent_node
from panda.core.workflow_manual.agents.replanner import replanner_node, replanner_router

from panda.core.llm.short_memory import checkpointer # mongodb per thread memory
from panda.core.llm import memory_extractor


def create_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner", planner_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("utility_agent", utility_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    # planner routes to supervisor OR directly to END for simple messages
    workflow.set_entry_point("planner")
    workflow.add_conditional_edges(
        "planner",
        lambda state: "end" if state.get("workflow_status") == "FINISHED" else "supervisor",
        {
            "end": END,
            "supervisor": "supervisor"
        }
    )
    
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "email_agent": "email_agent",
            "booking_agent": "booking_agent",
            "utility_agent": "utility_agent",
            "replanner": "replanner"
        }
    )
    
    workflow.add_edge("email_agent", "replanner")
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("utility_agent", "replanner")
    
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
    workflow = create_workflow() # TODO one time instantiate workflow

    app = workflow.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    current_state = await app.aget_state(config)

    # Check if graph is paused (resuming from an interrupt)
    if current_state.next:
        print(f"Resuming workflow for thread {thread_id} with: {user_input}")
        await app.ainvoke(
            Command(resume=user_input),
            config
        )
    else:
        # Fresh invocation
        if not current_state.values:
            payload = {
                "input": user_input,
                "messages": [HumanMessage(content=user_input)],
                "plan": [],
                "current_step_index": 0,
                "context": {},
                "last_tool_output": "",
                "final_response": "",
                "thread_id": thread_id
            }
        else:
            # continuing conversation from chat history (not interupt but same chat)
            payload = {
                "input": user_input,
                "messages": [HumanMessage(content=user_input)],
                "thread_id": thread_id,
                "workflow_status": None # for every calls force set not finished (bcz history may set it as finished)
            }

        print(f"User Request: {user_input}")
        
        await app.ainvoke(
            payload,
            config
        )

    # Check state AFTER invocation to see if graph paused at an interrupt
    state_after = await app.aget_state(config)

    if state_after.next:
        for task in state_after.tasks:
            if hasattr(task, 'interrupts') and task.interrupts:
                question = task.interrupts[0].value
                print(f"Graph interrupted: {question}")
                return {
                    "type": "interrupt",
                    "response": str(question),
                    "thread_id": thread_id,
                }
        # Fallback if we can't extract the interrupt value
        return {
            "type": "interrupt",
            "response": "I need more information to continue.",
            "thread_id": thread_id,
        }

    final_state = state_after.values
    print(final_state)

    # Append the AI's final response as a message so next turn sees it
    final_resp = final_state.get("final_response", "")
    if final_resp:
        await app.aupdate_state(
            config,
            {"messages": [AIMessage(content=final_resp)]}
        )

    # Extract key details from conversation and save to long-term memory
    try:
        conv_messages = final_state.get("messages", [])
        if conv_messages:
            await memory_extractor.extract_and_store(conv_messages, source="manual_chat")
    except Exception as e:
        print(f"Memory extraction skipped: {e}")
    
    return final_state