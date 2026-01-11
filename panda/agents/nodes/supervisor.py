from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from panda.core.llm.factory import LLMFactory, LLMProvider
from panda.core.llm.prompts import MASTER_SUPERVISOR_PROMPT
from panda.models.agents.state import MasterState
from panda.models.agents.response import SupervisorRouterResponse




supervisor_prompt = ChatPromptTemplate.from_messages([
        ("system", MASTER_SUPERVISOR_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])

async def supervisor_node(state: MasterState):
    llm_client = LLMFactory.get_client_for_agent("supervisor")
    supervisor_llm = llm_client.with_structured_output(SupervisorRouterResponse)
    
    chain = supervisor_prompt | supervisor_llm
    
    decision = await chain.ainvoke({
        "messages": state["messages"]
    })

    return {"next_step": decision.next_step}