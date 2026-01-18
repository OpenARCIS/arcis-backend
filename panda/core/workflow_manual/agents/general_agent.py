from langchain_core.prompts import ChatPromptTemplate
from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.core.llm.prompts import GENERAL_AGENT_PROMPT

from panda.core.workflow_manual.tools.web_search import web_search
from panda.core.workflow_manual.tools.calendar import calendar_tools


general_tools = [web_search] + calendar_tools 


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
    max_iterations = 10
    
    for i in range(max_iterations):
        # Invoke LLM
        response = await general_llm.ainvoke(messages)
        
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
        tool_output = final_response.content

    print(f"   Result: {tool_output}\n")
    
    return {
        **state,
        "last_tool_output": tool_output
    }