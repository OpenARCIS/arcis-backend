from typing import List
from langchain_core.prompts import ChatPromptTemplate

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState, PlanStep
from panda.models.agents.response import PlanModel
from panda.core.llm.prompts import PLANNER_PROMPT


async def planner_node(state: AgentState) -> AgentState:
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_PROMPT),
        ("human", "User Request: {input}\n\nGenerate a detailed execution plan.")
    ])
    
    
    llm_client = LLMFactory.get_client_for_agent("planner")
    planner_llm = llm_client.with_structured_output(PlanModel)

    messages = planner_prompt.format_messages(input=state["input"])
    plan_response = await planner_llm.ainvoke(messages)
    
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