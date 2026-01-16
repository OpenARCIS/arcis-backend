from langchain_core.prompts import ChatPromptTemplate
from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.core.llm.prompts import BOOKING_AGENT_PROMPT
#....... import booking_tools


async def booking_agent_node(state: AgentState) -> AgentState:
    
    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )
    
    if not current_step:
        return {**state, "last_tool_output": "ERROR: No in-progress step found"}
    
    booking_prompt = ChatPromptTemplate.from_messages([
        ("system", BOOKING_AGENT_PROMPT),
        ("human", """Current Task: {task_description}

Available Context:
{context}

Execute this booking/travel task. Provide detailed results.""")
    ])
    
    llm_client = LLMFactory.get_client_for_agent("booking_agent")
    #booking_llm = llm_client.bind_tools(booking_tools)
    
    messages = booking_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {}))
    )
    
    print(f"\n🎫 BOOKING AGENT: Executing - {current_step['description']}")
    tool_output = f"Booking task completed: {current_step['description']}"
    print(f"   Result: {tool_output}\n")
    
    return {
        **state,
        "last_tool_output": tool_output
    }
