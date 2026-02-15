from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState, PlanStep
from panda.models.agents.response import PlanModel
from panda.core.llm.prompts import PLANNER_PROMPT
from panda.core.utils.token_tracker import save_token_usage
from panda.core.utils.emotion_tracker import save_user_emotion
from panda.core.llm.long_memory import long_memory


def _format_history(messages: list, max_turns: int = 10) -> str:
    """Format recent messages into a readable conversation string for the prompt."""
    if not messages:
        return "(No prior conversation)"
    
    # Take only the last N messages to avoid prompt bloat
    recent = messages[-max_turns:]
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")
    
    return "\n".join(lines) if lines else "(No prior conversation)"


def _format_memories(memories: list) -> str:
    """Format long-term memory results into context text."""
    if not memories:
        return ""
    lines = [f"- {m['text']}" for m in memories]
    return "\n".join(lines)


async def planner_node(state: AgentState) -> AgentState:
    
    history = _format_history(state.get("messages", []))

    # Fetch relevant long-term memories
    long_term_context = ""
    try:
        if long_memory.client:
            memories = long_memory.search(state["input"], top_k=5)
            long_term_context = _format_memories(memories)
            if long_term_context:
                print(f"🧠 Long-term memory: found {len(memories)} relevant memories")
    except Exception as e:
        print(f"⚠️ Long-term memory lookup failed: {e}")
    
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_PROMPT),
        ("human", """Conversation History:
{history}

User Context (from long-term memory):
{long_term_context}

Latest User Request: {input}

Generate a detailed execution plan.""")
    ])
    
    
    llm_client = LLMFactory.get_client_for_agent("planner")
    planner_llm = llm_client.with_structured_output(PlanModel, include_raw=True)

    messages = planner_prompt.format_messages(
        input=state["input"],
        history=history,
        long_term_context=long_term_context or "(No stored context)",
    )
    response = await planner_llm.ainvoke(messages)
    
    plan_response = response["parsed"]
    
    # Save token usage
    if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
        await save_token_usage("planner", response["raw"].usage_metadata)

    # Save user emotion
    if plan_response.user_emotion:
        await save_user_emotion(plan_response.user_emotion, state["input"])
    
    plan_steps: List[PlanStep] = [
        {
            "id": idx + 1,
            "description": step.description,
            "status": "pending",
            "assigned_agent": step.assigned_agent
        }
        for idx, step in enumerate(plan_response.steps)
    ]
    
    print(f"\n{'='*60}")
    print(f"📋 PLANNER: Generated {len(plan_steps)} steps")
    for step in plan_steps:
        print(f"  {step['id']}. [{step['assigned_agent']}] {step['description']}")
    print(f"{'='*60}\n")
    
    # Inject long-term memories into context so agents can use them
    ctx = {}
    if long_term_context:
        ctx["long_term_memory"] = long_term_context

    return {
        **state,
        "plan": plan_steps,
        "current_step_index": 0,
        "context": ctx,
    }
