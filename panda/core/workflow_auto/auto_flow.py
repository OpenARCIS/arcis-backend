import uuid

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from panda.models.agents.state import AgentState
from panda.core.workflow_auto.nodes.analyzer import analyzer_node
from panda.core.workflow_manual.agents.supervisor import supervisor_node, supervisor_router
from panda.core.workflow_manual.agents.email_agent import email_agent_node
from panda.core.workflow_manual.agents.booking_agent import booking_agent_node
from panda.core.workflow_manual.agents.general_agent import general_agent_node
from panda.core.workflow_manual.agents.replanner import replanner_node, replanner_router
from panda.core.external_api.gmail import gmail_api

from panda.core.llm.short_memory import checkpointer
from panda.core.llm.pending_interrupt import save_pending, get_pending_by_id, resolve_pending


def create_auto_workflow() -> StateGraph:

    workflow = StateGraph(AgentState)
    
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("email_agent", email_agent_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("general_agent", general_agent_node)
    workflow.add_node("replanner", replanner_node)
    
    workflow.set_entry_point("analyzer")
    
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
    
    workflow.add_edge("email_agent", "replanner")
    workflow.add_edge("booking_agent", "replanner")
    workflow.add_edge("general_agent", "replanner")
    
    workflow.add_conditional_edges(
        "replanner",
        replanner_router,
        {
            "continue": "supervisor",
            "end": END
        }
    )
    
    return workflow


def _compile_auto_app():
    """Compile the auto workflow with checkpointer."""
    workflow = create_auto_workflow()
    return workflow.compile(checkpointer=checkpointer)


async def _check_and_save_interrupt(app, config, source_context: dict) -> bool:
    """
    Check if the graph hit an interrupt after ainvoke.
    If so, save it to pending_interrupts and return True.
    """
    state_after = await app.aget_state(config)
    thread_id = config["configurable"]["thread_id"]

    if state_after.next:
        for task in state_after.tasks:
            if hasattr(task, 'interrupts') and task.interrupts:
                question = str(task.interrupts[0].value)
                print(f"⏸️ Auto flow interrupted: {question}")
                save_pending(thread_id, question, source_context)
                return True
        # Fallback
        save_pending(thread_id, "Agent needs more information.", source_context)
        return True

    return False


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

    app = _compile_auto_app()

    for email in emails:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        print("\n" + "-"*50)
        print(f"📨 Processing Email: {email['subject']} (from: {email['sender']})")
        
        user_input = f"""
        Subject: {email['subject']}
        From: {email['sender']}
        Body:
        {email['body']}
        """

        initial_state: AgentState = {
            "input": user_input,
            "plan": [],
            "context": {"source_email": email},
            "last_tool_output": "",
            "final_response": "",
            "current_step_index": 0,
            "thread_id": thread_id
        }
        
        await app.ainvoke(initial_state, config)

        # Check if graph paused at an interrupt
        source_context = {
            "subject": email.get("subject", ""),
            "sender": email.get("sender", ""),
        }
        was_interrupted = await _check_and_save_interrupt(app, config, source_context)

        if was_interrupted:
            print(f"📋 Saved to pending items for user review.")
        else:
            state_after = await app.aget_state(config)
            final = state_after.values
            status = final.get('workflow_status', 'Unknown')
            print(f"🏁 Processing status: {status}")
            if status == 'FINISHED' and final.get('plan'):
                print("✅ Actions taken.")
            else:
                print("ℹ️ Ignored/No actions.")
                 
    print("\n" + "="*80)
    print("✅ BATCH PROCESSING COMPLETE")
    print("="*80)


async def resolve_interrupt(interrupt_id: str, user_answer: str) -> dict:
    """
    Resume a paused auto-flow graph with the user's answer.
    Called from the pending items API.
    """
    pending = get_pending_by_id(interrupt_id)
    if not pending:
        return {"status": "error", "message": "Pending item not found"}

    if pending["status"] != "pending":
        return {"status": "error", "message": f"Item already {pending['status']}"}

    thread_id = pending["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    app = _compile_auto_app()

    print(f"▶️ Resolving interrupt {interrupt_id} for thread {thread_id}")
    print(f"   User answer: {user_answer}")

    await app.ainvoke(Command(resume=user_answer), config)

    # Check if another interrupt was triggered
    source_context = pending.get("source_context", {})
    was_interrupted = await _check_and_save_interrupt(app, config, source_context)

    if was_interrupted:
        resolve_pending(interrupt_id)
        return {"status": "interrupted_again", "message": "Agent needs more info. New pending item created."}

    # Completed successfully
    resolve_pending(interrupt_id)

    state_after = await app.aget_state(config)
    final = state_after.values
    
    return {
        "status": "resolved",
        "message": final.get("final_response", "Task completed."),
        "workflow_status": final.get("workflow_status", "FINISHED")
    }
