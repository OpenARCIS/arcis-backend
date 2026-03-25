from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from datetime import datetime, timezone
from langgraph.types import interrupt

from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState
from arcis.core.mcp.manager import mcp_manager
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER
from arcis.core.llm.prompts.mcp import MCP_AGENT_PROMPT


async def mcp_agent_node(state: AgentState) -> AgentState:
    """Execute a task using dynamically discovered MCP tools."""

    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )

    if not current_step:
        return {**state, "last_tool_output": "ERROR: No in-progress step found"}

    mcp_tools = mcp_manager.get_tools_for_task(current_step["description"])

    if not mcp_tools:
        LOGGER.warning("MCP AGENT: No MCP tools available")
        return {
            **state,
            "last_tool_output": "ERROR: No MCP tools are available. Ensure MCP servers are configured and connected.",
        }

    LOGGER.info(f"MCP AGENT: Executing - {current_step['description']}")
    LOGGER.info(f"MCP AGENT: {len(mcp_tools)} tools available: {[t.name for t in mcp_tools]}")

    mcp_prompt = ChatPromptTemplate.from_messages([
        ("system", MCP_AGENT_PROMPT),
        ("human", """Current Task: {task_description}

Available Context:
{context}

Available MCP Tools: {tool_names}

Execute this task using the MCP tools available to you. Provide a detailed response.""")
    ])

    llm_client = LLMFactory.get_client_for_agent("mcp_agent")
    mcp_llm = llm_client.bind_tools(mcp_tools)

    messages = mcp_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {})),
        tool_names=", ".join(t.name for t in mcp_tools),
    )
    
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    messages.insert(1, SystemMessage(content=f"Current Date and Time is: {current_time}"))

    tool_output = ""
    max_iterations = 10

    for i in range(max_iterations):
        # On the last iteration, force a final answer
        if i == max_iterations - 1:
            messages.append(HumanMessage(
                content="You have reached the maximum number of tool iterations. "
                        "Do NOT call any more tools. Synthesize a final answer from the information you have gathered so far."
            ))
            LOGGER.warning(f"MCP AGENT: Reached max iterations ({max_iterations}), forcing final answer")
            final_response = await llm_client.ainvoke(messages)
            if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
                await save_token_usage("mcp_agent", final_response.usage_metadata)
            tool_output = final_response.content
            break

        # Invoke LLM
        response = await mcp_llm.ainvoke(messages)

        # Save token usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            await save_token_usage("mcp_agent", response.usage_metadata)
        elif hasattr(response, "response_metadata") and response.response_metadata.get("token_usage"):
            await save_token_usage("mcp_agent", response.response_metadata.get("token_usage"))

        # Check if agent needs user input
        if response.content and "[NEED_INPUT]" in response.content:
            question = response.content.replace("[NEED_INPUT]", "").strip()
            LOGGER.info(f"MCP AGENT needs user input: {question}")
            user_answer = interrupt(question)

            LOGGER.debug(f"User provided: {user_answer}")
            messages.append(response)
            messages.append(HumanMessage(content=f"User provided: {user_answer}"))
            response = await mcp_llm.ainvoke(messages)

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                await save_token_usage("mcp_agent", response.usage_metadata)

        # If no tool calls, we are done
        if not response.tool_calls:
            tool_output = response.content
            LOGGER.debug(f"MCP AGENT(final): {tool_output}")
            break

        # Execute tool calls
        tool_map = {tool.name: tool for tool in mcp_tools}
        tool_results = []

        LOGGER.debug(f"Iteration {i+1}: Processing {len(response.tool_calls)} tool calls")

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            LOGGER.debug(f"🔧 Calling MCP tool: {tool_name} with args: {tool_args}")

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
                LOGGER.warning(f"MCP tool {tool_name} not found in available tools")

        tool_messages = [
            ToolMessage(content=str(r.get('result', r.get('error'))), tool_call_id=tc["id"])
            for tc, r in zip(response.tool_calls, tool_results)
        ]

        # Append to history
        messages.append(response)
        messages.extend(tool_messages)

    # Safety fallback if loop ended without final answer
    if not tool_output and messages and isinstance(messages[-1], ToolMessage):
        final_response = await mcp_llm.ainvoke(messages)

        if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
            await save_token_usage("mcp_agent", final_response.usage_metadata)

        tool_output = final_response.content
        LOGGER.debug(f"MCP AGENT(final after loop): {tool_output}")

    # Accumulate output into shared context
    updated_context = dict(state.get("context", {}))
    step_key = current_step["description"]
    updated_context[step_key] = tool_output

    return {
        **state,
        "last_tool_output": tool_output,
        "context": updated_context
    }
