from langgraph.graph import StateGraph, END

from panda.models.agents.state import AgentState
from panda.core.workflow_auto.nodes.analyzer import analyzer_node
from panda.core.workflow_manual.agents.supervisor import supervisor_node, supervisor_router
from panda.core.workflow_manual.agents.email_agent import email_agent_node
from panda.core.workflow_manual.agents.booking_agent import booking_agent_node
from panda.core.workflow_manual.agents.general_agent import general_agent_node
from panda.core.workflow_manual.agents.replanner import replanner_node, replanner_router
from panda.core.external_api.gmail import gmail_api

# Reusing the exact same graph structure as manual flow, 
# but replacing 'planner' with 'analyzer'

def create_auto_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("general_agent", general_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    # Define edges
    workflow.set_entry_point("analyzer")
    
    # Analyzer -> Supervisor (if plan) or END (if ignored)
    def analyzer_router(state: AgentState):
        if state.get("workflow_status") == "FINISHED":
            return END
        return "supervisor"

    workflow.add_conditional_edges(
        "analyzer",
        analyzer_router,
        {
            "supervisor": "supervisor",
            END: END
        }
    )
    
    # Conditional routing from supervisor (Same as manual)
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "email_agent": "email_agent",
            "booking_agent": "booking_agent",
            "general_agent": "general_agent",
            "replanner": "replanner"
        }
    )
    
    # All workers route to replanner
    workflow.add_edge("email_agent", "replanner")
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("general_agent", "replanner")
    
    # Conditional routing from replanner
    workflow.add_conditional_edges(
        "replanner",
        replanner_router,
        {
            "continue": "supervisor",
            "end": END
        }
    )
    
    return workflow


async def run_autonomous_processing():
    """
    Main entry point for autonomous email processing.
    """
    print("\n" + "="*80)
    print("🤖 STARTING AUTONOMOUS EMAIL PROCESSING")
    print("="*80)
    
    try:
        emails = await gmail_api.get_n_mails(3)
        print(f"📥 Found {len(emails)} unread emails.")
    except Exception as e:
        print(f"❌ Error fetching emails: {e}")
        return

    if not emails:
        print("No emails to process.")
        return

    # 2. Compile workflow
    workflow = create_auto_workflow()
    app = workflow.compile()

    # 3. Process each email
    for email in emails:
        print("\n" + "-"*50)
        print(f"📨 Processing Email: {email['subject']} (from: {email['sender']})")
        
        # Construct input
        # We can format it nicely
        user_input = f"""
        Subject: {email['subject']}
        From: {email['sender']}
        Body:
        {email['body']}
        """

        initial_state: AgentState = {
            "input": user_input,
            "plan": [],
            "context": {"source_email": email}, # Add email metadata to context
            "last_tool_output": "",
            "final_response": "",
            "current_step_index": 0
        }
        
        # Run workflow
        final_state = await app.ainvoke(initial_state)
        
        print(f"🏁 Processing status: {final_state.get('workflow_status', 'Unknown')}")
        if final_state.get('workflow_status') == 'FINISHED' and final_state.get('plan'):
             print("✅ Actions taken.")
        else:
             print("ℹ️ Ignored/No actions.")
             
    print("\n" + "="*80)
    print("✅ BATCH PROCESSING COMPLETE")
    print("="*80)
