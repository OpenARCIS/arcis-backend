from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage

from panda.core.llm.factory import LLMFactory
from panda.models.agents.state import AgentState
from panda.core.llm.prompts import EMAIL_AGENT_PROMPT
from panda.core.workflow.tools.email import email_tools


async def email_agent_node(state: AgentState) -> AgentState:

    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )
    
    if not current_step:
        return {**state, "last_tool_output": "ERROR: No in-progress step found"}
    
    email_prompt = ChatPromptTemplate.from_messages([
        ("system", EMAIL_AGENT_PROMPT),
        ("human", """Current Task: {task_description}

Available Context:
{context}

Execute this task. Use your email tools if needed. Provide a detailed response.""")
    ])
    
    llm_client = LLMFactory.get_client_for_agent("email_agent")
    email_llm = llm_client.bind_tools(email_tools)
    
    messages = email_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {}))
    )
    

    print(f"\n✉️ EMAIL AGENT: Executing - {current_step['description']}")
    email_response = await email_llm.ainvoke(messages)
    
    if email_response.tool_calls:
        tool_map = {tool.name: tool for tool in email_tools}
        
        tool_results = []
        
        # Execute each tool call
        for tool_call in email_response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            print(f"   🔧 Calling tool: {tool_name} with args: {tool_args}")
            
            # Get the tool and invoke it
            if tool_name in tool_map:
                tool = tool_map[tool_name]
                try:
                    # Invoke the tool (sync or async)
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

        tool_messages = [
            ToolMessage(content=str(r['result']), tool_call_id=tc["id"])
            for tc, r in zip(email_response.tool_calls, tool_results)
        ]
        
        # Invoke LLM again with tool results
        final_response = await email_llm.ainvoke(
            messages + [email_response] + tool_messages
        )

        tool_output = final_response.content
    else:
        tool_output = email_response.content
    
    print(f"   Result: {tool_output}\n")
    
    return {
        **state,
        "last_tool_output": tool_output
    }