from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState
from arcis.core.llm.prompts import BOOKING_AGENT_PROMPT
from arcis.core.workflow_manual.tools.booking import booking_tools
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


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
    
    LOGGER.info(f"BOOKING AGENT: Executing - {current_step['description']}")

    tool_output = ""
    max_iterations = 5
    
    for i in range(max_iterations):
        # On the last iteration, tell the LLM to stop using tools and produce a final answer
        if i == max_iterations - 1:
            messages.append(HumanMessage(
                content="You have reached the maximum number of tool iterations. "
                        "Do NOT call any more tools. Synthesize a final answer from the information you have gathered so far."
            ))
            LOGGER.warning(f"BOOKING AGENT: Reached max iterations ({max_iterations}), forcing final answer")
            final_response = await llm_client.ainvoke(messages)
            if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
                await save_token_usage("booking_agent", final_response.usage_metadata)
            tool_output = final_response.content
            break

        # Invoke LLM
        response = await booking_llm.ainvoke(messages)
        
        # Save token usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
                await save_token_usage("booking_agent", response.usage_metadata)
        elif hasattr(response, "response_metadata") and response.response_metadata.get("token_usage"):
                await save_token_usage("booking_agent", response.response_metadata.get("token_usage"))

        # Check if agent needs user input
        if response.content and "[NEED_INPUT]" in response.content:
            question = response.content.replace("[NEED_INPUT]", "").strip()
            LOGGER.info(f"BOOKING AGENT needs user input: {question}")
            user_answer = interrupt(question)

            LOGGER.debug(f"User provided: {user_answer}")
            messages.append(response)
            messages.append(HumanMessage(content=f"User provided: {user_answer}"))
            response = await booking_llm.ainvoke(messages)

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                await save_token_usage("booking_agent", response.usage_metadata)

        # If no tool calls, we are done
        if not response.tool_calls:
            tool_output = response.content
            break

        # Execute tool calls
        tool_map = {tool.name: tool for tool in booking_tools}
        tool_results = []
        
        LOGGER.debug(f"Iteration {i+1}: Processing {len(response.tool_calls)} tool calls")
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            LOGGER.debug(f"🔧 Calling tool: {tool_name} with args: {tool_args}")
            
            if tool_name in tool_map:
                tool = tool_map[tool_name]
                try:
                    if hasattr(tool, 'ainvoke'):
                        result = await tool.ainvoke(tool_args)
                    else:
                        result = tool.invoke(tool_args)
                    
                    tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                    LOGGER.debug(f"Tool result: {result}")
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    tool_results.append({
                        "tool": tool_name,
                        "error": error_msg
                    })
                    LOGGER.error(error_msg)
            else:
                LOGGER.warning(f"Tool {tool_name} not found")

        # Create tool messages
        from langchain_core.messages import ToolMessage
        tool_messages = [
            ToolMessage(content=str(r.get('result', r.get('error'))), tool_call_id=tc["id"])
            for tc, r in zip(response.tool_calls, tool_results)
        ]
        
        # Append to history
        messages.append(response)
        messages.extend(tool_messages)

    # Safety net: if loop ended without a final answer
    if not tool_output and messages and isinstance(messages[-1], ToolMessage):
        final_response = await booking_llm.ainvoke(messages)
        if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
            await save_token_usage("booking_agent", final_response.usage_metadata)
        tool_output = final_response.content

    LOGGER.debug(f"Result: {tool_output}")
    
    # Accumulate output into shared context so other agents can see it
    updated_context = dict(state.get("context", {}))
    step_key = current_step["description"]
    updated_context[step_key] = tool_output

    return {
        **state,
        "last_tool_output": tool_output,
        "context": updated_context
    }

