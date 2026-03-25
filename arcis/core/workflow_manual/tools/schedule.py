from datetime import datetime
from langchain.tools import tool

from arcis.models.scheduler.job_models import ScheduledJob, JobType
from arcis.core.scheduler.scheduler_service import scheduler_service


@tool
async def schedule_job(
    title: str,
    job_type: str,
    trigger_at: str,
    description: str = "",
    cron_expression: str = None,
    notification_message: str = "",
    needs_context_prefetch: bool = False,
    prefetch_queries: list[str] = None,
) -> str:
    """
    Schedules a new job (reminder, todo, event, or cron). This also creates a calendar entry automatically.

    Args:
        title: Short title for the job (e.g., "Call mom", "Team standup").
        job_type: One of 'reminder', 'todo', 'event', 'cron'.
        trigger_at: ISO 8601 datetime string for when the job should trigger (e.g., '2025-10-27T15:00:00').
        description: Optional detailed description of what needs to be done.
        cron_expression: Cron expression for recurring jobs (e.g., '0 9 * * 1' for every Monday 9am). Only needed when job_type is 'cron'.
        notification_message: Custom notification text. If empty, title will be used.
        needs_context_prefetch: Whether this job needs context gathering before triggering (e.g., web search, file lookup). Enable for research tasks, meeting prep, news digests.
        prefetch_queries: Search queries to use during context prefetch. Only relevant when needs_context_prefetch is True.
    """
    try:
        # Validate job type
        try:
            jtype = JobType(job_type.lower())
        except ValueError:
            return f"❌ Invalid job_type '{job_type}'. Must be one of: reminder, todo, event, cron."

        # Parse trigger time
        try:
            trigger_dt = datetime.fromisoformat(trigger_at)
        except ValueError:
            return f"❌ Invalid trigger_at '{trigger_at}'. Please use ISO 8601 format (YYYY-MM-DDTHH:MM:SS)."

        # Build the job
        job = ScheduledJob(
            job_type=jtype,
            title=title,
            description=description,
            trigger_at=trigger_dt,
            cron_expression=cron_expression if jtype == JobType.CRON else None,
            notification_message=notification_message or title,
        )

        if needs_context_prefetch and prefetch_queries:
            job.context["prefetch_queries"] = prefetch_queries

        # Register with scheduler service (also creates calendar entry)
        job_id = await scheduler_service.schedule_job(job)

        output = (
            f"✅ Scheduled successfully!\n"
            f"  Type: {jtype.value}\n"
            f"  Title: {title}\n"
            f"  Trigger: {trigger_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"  Job ID: {job_id}"
        )

        if needs_context_prefetch:
            output += f"\n  📎 Context prefetch enabled"
        if cron_expression and jtype == JobType.CRON:
            output += f"\n  🔄 Recurring: {cron_expression}"

        return output

    except Exception as e:
        return f"❌ Failed to schedule: {str(e)}"
