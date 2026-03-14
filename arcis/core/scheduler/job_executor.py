from arcis.core.scheduler.job_store import job_store
from arcis.core.scheduler.context_prefetcher import prefetch_context
from arcis.core.scheduler.notification_dispatcher import dispatcher
from arcis.models.scheduler.job_models import JobStatus, JobType
from arcis.logger import LOGGER


async def execute_job(job_id: str):
    """
    Main dispatcher — called by APScheduler for all job types.
    Routes to the appropriate handler based on job_type.
    """
    job = await job_store.get_job(job_id)
    if not job:
        LOGGER.warning(f"EXECUTOR: Job {job_id} not found, skipping")
        return

    status = job.get("status")
    if status in (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value):
        LOGGER.info(f"EXECUTOR: Job {job_id} is {status}, skipping")
        return

    job_type = job.get("job_type")
    LOGGER.info(f"EXECUTOR: Triggering job {job_id} [{job_type}] — {job.get('title')}")

    try:
        if job_type == JobType.REMINDER.value:
            await _execute_reminder(job_id, job)
        elif job_type in (JobType.TODO.value, JobType.EVENT.value):
            await _execute_todo_event(job_id, job)
        elif job_type == JobType.CRON.value:
            await _execute_cron(job_id, job)
        else:
            LOGGER.error(f"EXECUTOR: Unknown job type '{job_type}' for job {job_id}")
            await job_store.set_status(job_id, JobStatus.FAILED, error=f"Unknown job type: {job_type}")
    except Exception as e:
        LOGGER.error(f"EXECUTOR: Job {job_id} failed with error: {e}")
        await job_store.set_status(job_id, JobStatus.FAILED, error=str(e))


async def execute_prefetch(job_id: str):
    """
    Called by APScheduler when a job's prefetch_at time arrives.
    Gathers context and stores it on the job.
    """
    job = await job_store.get_job(job_id)
    if not job:
        LOGGER.warning(f"PREFETCH-EXEC: Job {job_id} not found")
        return

    if job.get("status") in (JobStatus.CANCELLED.value, JobStatus.COMPLETED.value):
        LOGGER.info(f"PREFETCH-EXEC: Job {job_id} is {job['status']}, skipping prefetch")
        return

    LOGGER.info(f"PREFETCH-EXEC: Starting context prefetch for job {job_id} — {job.get('title')}")
    await job_store.set_status(job_id, JobStatus.PREFETCHING)

    try:
        context = await prefetch_context(job)
        await job_store.store_context(job_id, context)
        LOGGER.info(f"PREFETCH-EXEC: Context stored for job {job_id}")
    except Exception as e:
        LOGGER.error(f"PREFETCH-EXEC: Failed for job {job_id}: {e}")
        # Don't fail the whole job — it can still trigger without context
        await job_store.set_status(job_id, JobStatus.READY)



async def _execute_reminder(job_id: str, job: dict):
    """Notification with optional prefetched context."""
    title = job.get("title", "Reminder")
    message = job.get("notification_message") or title
    description = job.get("description", "")
    context = job.get("context", {})

    body = f"🔔 {message}"
    if description:
        body += f"\n📝 {description}"

    # Include prefetched context if available
    if context:
        if "prefetch_response" in context:
            body += f"\n\n🧠 Prepared by AI:\n{context['prefetch_response']}"
        elif "web_search" in context:
            web_items = context["web_search"]
            body += f"\n\n📎 Context ({len(web_items)} sources):"
            for item in web_items[:3]:
                result_text = str(item.get("result", ""))[:200]
                body += f"\n  • {item.get('query', '')}: {result_text}"

    await dispatcher.send(title=f"Reminder: {title}", message=body, job_id=job_id, level="info")
    await job_store.set_status(job_id, JobStatus.COMPLETED)
    LOGGER.info(f"EXECUTOR: Reminder {job_id} sent successfully")


async def _execute_todo_event(job_id: str, job: dict):
    """
    Send notification with prefetched context.
    """
    title = job.get("title", "Task")
    job_type = job.get("job_type", "todo")
    description = job.get("description", "")
    context = job.get("context", {})

    # Build notification
    emoji = "📋" if job_type == JobType.TODO.value else "📅"
    body = f"{emoji} {job_type.title()}: {title}"
    
    if description:
        body += f"\n📝 {description}"

    # Include prefetched context
    if context:
        # Deep prefetch output (from planner graph)
        if "prefetch_response" in context:
            body += f"\n\n🧠 Prepared by AI:\n{context['prefetch_response']}"
        
        # Shallow fallback: web search results
        elif "web_search" in context:
            body += "\n\n📎 Prepared Context:"
            web_items = context["web_search"]
            body += f"\n🌐 Web Research ({len(web_items)} sources):"
            for item in web_items[:3]:
                result_text = str(item.get("result", ""))[:200]
                body += f"\n  • {item.get('query', '')}: {result_text}"
        
        # Long-term memory (available in both modes)
        if "long_term_memory" in context:
            memory_text = str(context["long_term_memory"])[:300]
            body += f"\n🧠 Related Memory:\n  {memory_text}"

    await dispatcher.send(title=f"{job_type.title()}: {title}", message=body, job_id=job_id, level="info")
    await job_store.set_status(job_id, JobStatus.COMPLETED)
    LOGGER.info(f"EXECUTOR: {job_type} {job_id} notified successfully")


async def _execute_cron(job_id: str, job: dict):
    """
    Cron jobs run recurrently. Execute the action and keep the job alive.
    For complex cron tasks, invoke manual_flow.
    """
    title = job.get("title", "Cron Job")
    description = job.get("description", "")

    # For cron jobs, we check if it needs a full workflow run
    needs_workflow = bool(description and len(description) > 50)

    if needs_workflow:
        # Run through the manual flow for complex tasks
        try:
            from arcis.core.workflow_manual.manual_flow import run_workflow
            import uuid
            thread_id = str(uuid.uuid4())
            
            result = await run_workflow(
                user_input=f"[Scheduled Task] {title}: {description}",
                thread_id=thread_id
            )
            
            final_response = ""
            if isinstance(result, dict):
                final_response = result.get("final_response", "Task executed")
            
            await dispatcher.send(
                title=title,
                message=final_response,
                job_id=job_id,
                level="success",
            )
        except Exception as e:
            LOGGER.error(f"EXECUTOR: Cron workflow failed for {job_id}: {e}")
            await dispatcher.send(
                title=f"Cron Job: {title}",
                message=f"⚙️ Cron Job: {title}\n❌ Error: {str(e)}",
                job_id=job_id,
                level="error",
            )
    else:
        # Simple cron: just notify
        await dispatcher.send(
            title=title,
            message=description,
            job_id=job_id,
            level="info",
        )

    # Don't mark cron jobs as completed — they keep running
    # APScheduler handles the recurrence via CronTrigger
    await job_store.update_job(job_id, {"status": JobStatus.TRIGGERED.value})
    LOGGER.info(f"EXECUTOR: Cron job {job_id} triggered successfully")