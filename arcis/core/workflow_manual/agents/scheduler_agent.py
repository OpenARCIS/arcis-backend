from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

from arcis.core.llm.factory import LLMFactory
from arcis.core.llm.prompts import SCHEDULER_AGENT_PROMPT
from arcis.models.agents.state import AgentState
from arcis.models.scheduler.job_models import ScheduledJob, SchedulerParseResult
from arcis.core.scheduler.scheduler_service import scheduler_service
from arcis.core.utils.token_tracker import save_token_usage
from arcis.logger import LOGGER


async def scheduler_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node that:
    1. Extracts the current plan step
    2. Uses LLM + structured output to parse scheduling parameters
    3. Creates a ScheduledJob and registers it with the scheduler service
    4. Returns confirmation in last_tool_output
    """

    current_step = next(
        (s for s in state["plan"] if s["status"] == "in_progress"),
        None
    )

    if not current_step:
        return {**state, "last_tool_output": "ERROR: No in-progress step found for scheduler"}

    # Build prompt with context
    scheduler_prompt = ChatPromptTemplate.from_messages([
        ("system", SCHEDULER_AGENT_PROMPT),
        ("human", """Current Task: {task_description}

Available Context:
{context}

Current Date/Time: {current_time}

Parse this into scheduling parameters.""")
    ])

    llm_client = LLMFactory.get_client_for_agent("scheduler_agent")
    scheduler_llm = llm_client.with_structured_output(SchedulerParseResult, include_raw=True)

    LOGGER.info(f"SCHEDULER AGENT: Parsing — {current_step['description']}")

    messages = scheduler_prompt.format_messages(
        task_description=current_step["description"],
        context=str(state.get("context", {})),
        current_time=datetime.now().isoformat()
    )

    response = await scheduler_llm.ainvoke(messages)
    parsed: SchedulerParseResult = response["parsed"]

    # Save token usage
    if response.get("raw") and hasattr(response["raw"], "usage_metadata"):
        await save_token_usage("scheduler_agent", response["raw"].usage_metadata)

    LOGGER.info(f"SCHEDULER AGENT: Parsed — type={parsed.job_type.value}, "
                f"trigger_at={parsed.trigger_at}, title='{parsed.title}'")

    # Create the ScheduledJob
    job = ScheduledJob(
        job_type=parsed.job_type,
        title=parsed.title,
        description=parsed.description,
        trigger_at=parsed.trigger_at,
        cron_expression=parsed.cron_expression,
        notification_message=parsed.notification_message or parsed.title,
        thread_id=state.get("thread_id"),
    )

    # Embed prefetch queries in context if provided
    if parsed.needs_context_prefetch and parsed.prefetch_queries:
        job.context["prefetch_queries"] = parsed.prefetch_queries

    # Register with the scheduler service
    try:
        job_id = await scheduler_service.schedule_job(job)
        
        output = (
            f"✅ Scheduled successfully!\n"
            f"  Type: {parsed.job_type.value}\n"
            f"  Title: {parsed.title}\n"
            f"  Trigger: {parsed.trigger_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"  Job ID: {job_id}"
        )
        
        if parsed.needs_context_prefetch:
            output += f"\n  📎 Context prefetch enabled (queries: {parsed.prefetch_queries})"
        if parsed.cron_expression:
            output += f"\n  🔄 Recurring: {parsed.cron_expression}"
            
    except Exception as e:
        LOGGER.error(f"SCHEDULER AGENT: Failed to schedule job: {e}")
        output = f"❌ Failed to schedule: {str(e)}"

    LOGGER.info(f"SCHEDULER AGENT: {output}")

    # Accumulate output into shared context
    updated_context = dict(state.get("context", {}))
    step_key = current_step["description"]
    updated_context[step_key] = output

    return {
        **state,
        "last_tool_output": output,
        "context": updated_context
    }
