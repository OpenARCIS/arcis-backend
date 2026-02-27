from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import interrupt

from arcis.core.llm.factory import LLMFactory
from arcis.models.agents.state import AgentState
from arcis.core.llm.prompts import EMAIL_AGENT_PROMPT
from arcis.core.workflow_manual.tools.email import email_tools
from arcis.core.utils.token_tracker import save_token_usage


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
    
    print(f"\n✉️ EMAIL AGENT: Executing - {current_step['description']}")

    # Track conversation
    messages = email_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {}))
    )

    tool_output = ""
    max_iterations = 10
    
    for i in range(max_iterations):
        # On the last iteration, tell the LLM to stop using tools and produce a final answer
        if i == max_iterations - 1:
            messages.append(HumanMessage(
                content="You have reached the maximum number of tool iterations. "
                        "Do NOT call any more tools. Synthesize a final answer from the information you have gathered so far."
            ))
            print(f"   ⚠️ EMAIL AGENT: Reached max iterations ({max_iterations}), forcing final answer")
            final_response = await llm_client.ainvoke(messages)
            if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
                await save_token_usage("email_agent", final_response.usage_metadata)
            tool_output = final_response.content
            break

        # Invoke LLM
        email_response = await email_llm.ainvoke(messages)
        
        # Save token usage
        if hasattr(email_response, "usage_metadata") and email_response.usage_metadata:
             await save_token_usage("email_agent", email_response.usage_metadata)
        elif hasattr(email_response, "response_metadata") and email_response.response_metadata.get("token_usage"):
             await save_token_usage("email_agent", email_response.response_metadata.get("token_usage"))
        
        # Check if agent needs user input
        if email_response.content and "[NEED_INPUT]" in email_response.content:
            question = email_response.content.replace("[NEED_INPUT]", "").strip()
            print(f"   ❓ EMAIL AGENT needs user input: {question}")
            user_answer = interrupt(question)

            print(f"   ✅ User provided: {user_answer}")
            messages.append(email_response)
            messages.append(HumanMessage(content=f"User provided: {user_answer}"))
            email_response = await email_llm.ainvoke(messages)

            if hasattr(email_response, "usage_metadata") and email_response.usage_metadata:
                await save_token_usage("email_agent", email_response.usage_metadata)

        # If no tool calls, we are done
        if not email_response.tool_calls:
            tool_output = email_response.content
            print("EMAIL AGENT(final) : ", tool_output)
            break

        tool_map = {tool.name: tool for tool in email_tools}
        tool_results = []
        
        print(f"   🔄 Iteration {i+1}: Processing {len(email_response.tool_calls)} tool calls")
        
        # Execute each tool call
        for tool_call in email_response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
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
            ToolMessage(content=str(r.get('result', r.get('error'))), tool_call_id=tc["id"])
            for tc, r in zip(email_response.tool_calls, tool_results)
        ]
        
        # Append to history
        messages.append(email_response)
        messages.extend(tool_messages)

    # If loop finished but still no final answer (should be rare if agent follows instructions, but good safety)
    if not tool_output and messages and isinstance(messages[-1], ToolMessage):
         # One final call
        final_response = await email_llm.ainvoke(messages)
        
        # Save token usage (final)
        if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
             await save_token_usage("email_agent", final_response.usage_metadata)

        tool_output = final_response.content
        print("EMAIL AGENT(final after loop) : ", tool_output)
    
    # Accumulate output into shared context so other agents can see it
    updated_context = dict(state.get("context", {}))
    step_key = current_step["description"]
    updated_context[step_key] = tool_output

    return {
        **state,
        "last_tool_output": tool_output,
        "context": updated_context
    }