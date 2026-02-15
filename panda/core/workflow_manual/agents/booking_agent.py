from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.core.llm.prompts import BOOKING_AGENT_PROMPT
from panda.core.workflow_manual.tools.booking import booking_tools
from panda.core.utils.token_tracker import save_token_usage


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
    booking_llm = llm_client.bind_tools(booking_tools)
    
    messages = booking_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {}))
    )
    
    print(f"\n🎫 BOOKING AGENT: Executing - {current_step['description']}")

    # Initial LLM call
    response = await booking_llm.ainvoke(messages)
    
    # Save token usage
    if hasattr(response, "usage_metadata") and response.usage_metadata:
            await save_token_usage("booking_agent", response.usage_metadata)
    elif hasattr(response, "response_metadata") and response.response_metadata.get("token_usage"):
            await save_token_usage("booking_agent", response.response_metadata.get("token_usage"))

    # Check if agent needs user input
    if response.content and "[NEED_INPUT]" in response.content:
        question = response.content.replace("[NEED_INPUT]", "").strip()
        print(f"   ❓ BOOKING AGENT needs user input: {question}")
        user_answer = interrupt(question)  # Graph PAUSES here

        # Graph RESUMES here when user replies
        print(f"   ✅ User provided: {user_answer}")
        messages.append(response)
        messages.append(HumanMessage(content=f"User provided: {user_answer}"))
        response = await booking_llm.ainvoke(messages)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            await save_token_usage("booking_agent", response.usage_metadata)
    
    tool_output = ""
    
    # Handle tool calls if any
    if response.tool_calls:
        # Create a map of available tools
        tool_map = {tool.name: tool for tool in booking_tools}
        
        tool_results = []
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"   🔧 Calling tool: {tool_name} with args: {tool_args}")
            
            if tool_name in tool_map:
                tool = tool_map[tool_name]
                try:
                    # All mock tools are synchronous, but good to be safe with invoke
                    if hasattr(tool, 'ainvoke'):
                        result = await tool.ainvoke(tool_args)
                    else:
                        result = tool.invoke(tool_args)
                    
                    tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                    print(f"   ✅ Tool result: {result}")
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    tool_results.append({
                        "tool": tool_name,
                        "error": error_msg
                    })
                    print(f"   ❌ {error_msg}")
            else:
                print(f"   ⚠️ Tool {tool_name} not found")

        # Create tool messages
        from langchain_core.messages import ToolMessage
        tool_messages = [
            ToolMessage(content=str(r.get('result', r.get('error'))), tool_call_id=tc["id"])
            for tc, r in zip(response.tool_calls, tool_results)
        ]
        
        # Get final response with tool outputs
        final_response = await booking_llm.ainvoke(
            messages + [response] + tool_messages
        )
        
        # Save token usage (final)
        if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
             await save_token_usage("booking_agent", final_response.usage_metadata)

        tool_output = final_response.content
    else:
        tool_output = response.content

    print(f"   Result: {tool_output}\n")
    
    # Accumulate output into shared context so other agents can see it
    updated_context = dict(state.get("context", {}))
    step_key = current_step["description"]
    updated_context[step_key] = tool_output

    return {
        **state,
        "last_tool_output": tool_output,
        "context": updated_context
    }
