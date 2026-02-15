from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState, PlanStep
from panda.models.agents.response import PlanModel
from panda.core.llm.prompts import PLANNER_PROMPT
from panda.core.utils.token_tracker import save_token_usage
from panda.core.utils.emotion_tracker import save_user_emotion


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


async def planner_node(state: AgentState) -> AgentState:
    
    history = _format_history(state.get("messages", []))
    
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_PROMPT),
        ("human", """Conversation History:
{history}

Latest User Request: {input}

Generate a detailed execution plan.""")
    ])
    
    
    llm_client = LLMFactory.get_client_for_agent("planner")
    planner_llm = llm_client.with_structured_output(PlanModel, include_raw=True)

    messages = planner_prompt.format_messages(input=state["input"], history=history)
    response = await planner_llm.ainvoke(messages)
    
    plan_response = response["parsed"]
    
    # Save token usage
    if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
        await save_token_usage("planner", response["raw"].usage_metadata)

    # Save user emotion
    if plan_response.user_emotion:
        await save_user_emotion(plan_response.user_emotion, state["input"])

    # Short-circuit for simple conversational messages
    if plan_response.is_conversational:
        print(f"\n{'='*60}")
        print(f"💬 PLANNER: Conversational message detected — skipping agent loop")
        print(f"   Response: {plan_response.direct_response}")
        print(f"{'='*60}\n")
        return {
            **state,
            "plan": [],
            "current_step_index": 0,
            "context": {},
            "final_response": plan_response.direct_response or "",
            "workflow_status": "FINISHED"
        }
    
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
    
    return {
        **state,
        "plan": plan_steps,
        "current_step_index": 0,
        "context": {}
    }
