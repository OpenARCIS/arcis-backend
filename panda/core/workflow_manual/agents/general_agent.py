from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.core.llm.prompts import GENERAL_AGENT_PROMPT
from panda.core.utils.token_tracker import save_token_usage

from panda.core.workflow_manual.tools.web_search import web_search
from panda.core.workflow_manual.tools.calendar import calendar_tools
from panda.core.workflow_manual.tools.memory_search import memory_search


general_tools = [web_search, memory_search] + calendar_tools 


async def general_agent_node(state: AgentState) -> AgentState:
    
    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )
    
    if not current_step:
        return {**state, "last_tool_output": "ERROR: No in-progress step found"}
    
    general_prompt = ChatPromptTemplate.from_messages([
        ("system", GENERAL_AGENT_PROMPT),
        ("human", """Current Task: {task_description}

Available Context:
{context}

Execute this task and gather necessary information.""")
    ])
    
    llm_client = LLMFactory.get_client_for_agent("general_agent")
    general_llm = llm_client.bind_tools(general_tools)
    
    print(f"\n🔧 GENERAL AGENT: Executing - {current_step['description']}")
    
    # Track the ongoing conversation
    messages = general_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {}))
    )
    
    tool_output = ""
    max_iterations = 3
    
    for i in range(max_iterations):
        # On the last iteration, tell the LLM to stop using tools and produce a final answer
        if i == max_iterations - 1:
            messages.append(HumanMessage(
                content="You have reached the maximum number of tool iterations. "
                        "Do NOT call any more tools. Synthesize a final answer from the information you have gathered so far."
            ))
            print(f"   ⚠️ GENERAL AGENT: Reached max iterations ({max_iterations}), forcing final answer")
            final_response = await llm_client.ainvoke(messages)
            if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
                await save_token_usage("general_agent", final_response.usage_metadata)
            tool_output = final_response.content
            break

        # Invoke LLM
        response = await general_llm.ainvoke(messages)
        
        # Save token usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
             await save_token_usage("general_agent", response.usage_metadata)
        elif hasattr(response, "response_metadata") and response.response_metadata.get("token_usage"):
             await save_token_usage("general_agent", response.response_metadata.get("token_usage"))
        
        # Check if agent needs user input
        if response.content and "[NEED_INPUT]" in response.content:
            question = response.content.replace("[NEED_INPUT]", "").strip()
            print(f"   ❓ GENERAL AGENT needs user input: {question}")
            user_answer = interrupt(question)

            print(f"   ✅ User provided: {user_answer}")
            messages.append(response)
            messages.append(HumanMessage(content=f"User provided: {user_answer}"))
            response = await general_llm.ainvoke(messages)

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                await save_token_usage("general_agent", response.usage_metadata)

        # If no tool calls, we are done
        if not response.tool_calls:
            tool_output = response.content
            break
            
        # If there are tool calls, execute them
        tool_map = {tool.name: tool for tool in general_tools}
        tool_results = []
        
        print(f"   🔄 Iteration {i+1}: Processing {len(response.tool_calls)} tool calls")
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"   🔧 Calling tool: {tool_name} with args: {tool_args}")
            
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
        
        # Append the assistant's request and the tool outputs to the history
        messages.append(response)
        messages.extend(tool_messages)
    
    # If we exited the loop due to max iterations
    if not tool_output and messages and isinstance(messages[-1], ToolMessage):
         # One final call to get the answer based on the last tool outputs
        final_response = await general_llm.ainvoke(messages)
        
        # Save token usage (final)
        if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
             await save_token_usage("general_agent", final_response.usage_metadata)

        tool_output = final_response.content

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