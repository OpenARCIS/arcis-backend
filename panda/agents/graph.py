import asyncio
import operator
from typing import Annotated, List, TypedDict
from langgraph.graph import StateGraph, END
from panda.agents.nodes.supervisor import supervisor_node


class BaseMessage:
    def __init__(self, content, type="user"):
        self.content = content
        self.type = type
    def __repr__(self): return f"{self.type}: {self.content}"

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_step: str
    user_emotion: str


async def scheduler_node(state: AgentState):
    print("   --> [Scheduler] (Async) Checking calendar...")
    await asyncio.sleep(0.1) # Simulate IO delay
    return {"messages": [BaseMessage("Event scheduled.", "ai")]}

async def analyst_node(state: AgentState):
    print("   --> [Analyst] (Async) Analyzing DB logs...")
    await asyncio.sleep(0.1)
    return {"messages": [BaseMessage("Logs updated.", "ai")]}

async def communications_node(state: AgentState):
    print("   --> [Communications] (Async) Sending email...")
    await asyncio.sleep(0.1)
    return {"messages": [BaseMessage("Email sent.", "ai")]}

async def build_and_run_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Scheduler", scheduler_node)
    workflow.add_node("Analyst", analyst_node)
    workflow.add_node("Communications", communications_node)

    workflow.set_entry_point("Supervisor")

    workflow.add_conditional_edges(
        "Supervisor",
        lambda state: state["next_step"],
        {
            "Scheduler": "Scheduler",
            "Analyst": "Analyst",
            "Communications": "Communications"
        }
    )

    workflow.add_edge("Scheduler", END)
    workflow.add_edge("Analyst", END)
    workflow.add_edge("Communications", END)

    app = workflow.compile()

    print("=== STARTING ASYNC GRAPH TESTS ===")

    # Test 1: Scheduler Intent
    print("\n--- Test 1 ---")
    inputs = {"messages": [BaseMessage("Book a meeting with Alice")]}
    
    await app.ainvoke(inputs)

    print("\n--- Test 2 ---")
    inputs = {"messages": [BaseMessage("I am feeling very stressed today")]}
    await app.ainvoke(inputs)