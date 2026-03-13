from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from arcis.core.llm.short_memory import db_client  # sync PyMongo client
from arcis import Config
from arcis.core.scheduler.job_store import job_store
from arcis.core.scheduler.job_executor import execute_job, execute_prefetch
from arcis.models.scheduler.job_models import ScheduledJob, JobType
from arcis.core.external_api.internal_calendar import calendar_wrapper, CalendarItem
from arcis.logger import LOGGER


# Prefetch lead time in minutes (how far before trigger_at to start context gathering)
PREFETCH_LEAD_MINUTES = int(getattr(Config, 'SCHEDULER_PREFETCH_LEAD_MINUTES', 120))


class SchedulerService:
    """Manages APScheduler lifecycle and job registration."""

    def __init__(self):
        self.scheduler: AsyncIOScheduler | None = None

    async def start(self):
        """Initialize and start APScheduler with MongoDB job store."""
        try:
            mongo_jobstore = MongoDBJobStore(
                client=db_client,
                database=Config.DATABASE_NAME,
                collection="apscheduler_jobs"
            )

            self.scheduler = AsyncIOScheduler(
                jobstores={"default": mongo_jobstore},
                job_defaults={
                    "coalesce": True,      # merge missed runs into one
                    "max_instances": 1,     # prevent overlapping
                    "misfire_grace_time": 300  # 5 min grace for missed triggers
                }
            )
            self.scheduler.start()
            LOGGER.info("SCHEDULER: APScheduler started successfully")

            # Re-hydrate any pending jobs from our metadata store
            await self._rehydrate_jobs()
        except Exception as e:
            LOGGER.error(f"SCHEDULER: Failed to start: {e}")
            raise

    async def shutdown(self):
        """Gracefully shut down the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            LOGGER.info("SCHEDULER: Shut down")

    async def schedule_job(self, job: ScheduledJob) -> str:
        """
        Register a new scheduled job:
        1. Save metadata to our job store (scheduled_jobs collection)
        2. Create calendar entry if appropriate
        3. Schedule APScheduler trigger(s)
        
        Returns the job ID.
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not started")

        # 1. If the scheduler agent provided prefetch queries, embed them in context
        # (They'll be used by the prefetcher later)
        if hasattr(job, '_prefetch_queries') and job._prefetch_queries:
            job.context["prefetch_queries"] = job._prefetch_queries

        # 2. Auto-calculate prefetch_at if needed but not set
        if job.job_type in (JobType.TODO, JobType.EVENT) and not job.prefetch_at:
            lead = timedelta(minutes=PREFETCH_LEAD_MINUTES)
            candidate = job.trigger_at - lead
            if candidate > datetime.now():
                job.prefetch_at = candidate

        # 3. Save to our metadata store
        job_id = await job_store.create_job(job)

        # 4. Create corresponding calendar entry
        try:
            calendar_type_map = {
                JobType.REMINDER: "reminder",
                JobType.TODO: "todo",
                JobType.EVENT: "event",
                JobType.CRON: "event",  # cron jobs show as events in calendar
            }
            cal_item = CalendarItem(
                title=job.title,
                item_type=calendar_type_map.get(job.job_type, "reminder"),
                start_time=job.trigger_at,
                description=job.description,
            )
            cal_id = await calendar_wrapper.add_item(cal_item)
            await job_store.update_job(job_id, {"calendar_item_id": cal_id})
            LOGGER.debug(f"SCHEDULER: Created calendar entry {cal_id} for job {job_id}")
        except Exception as e:
            LOGGER.warning(f"SCHEDULER: Calendar entry creation failed (non-fatal): {e}")

        # 5. Schedule APScheduler triggers
        if job.job_type == JobType.CRON and job.cron_expression:
            # Recurring cron trigger
            self._add_cron_trigger(job_id, job.cron_expression)
        else:
            # One-shot date trigger
            self._add_date_trigger(job_id, job.trigger_at, "main")

        # Schedule prefetch if applicable
        if job.prefetch_at and job.prefetch_at > datetime.now():
            self._add_prefetch_trigger(job_id, job.prefetch_at)

        LOGGER.info(f"SCHEDULER: Job {job_id} scheduled — "
                     f"type={job.job_type.value}, trigger_at={job.trigger_at}")
        return job_id

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job: remove from APScheduler and update metadata store."""
        # Remove APScheduler jobs
        for suffix in ["_main", "_prefetch"]:
            aps_id = f"job_{job_id}{suffix}"
            try:
                if self.scheduler:
                    self.scheduler.remove_job(aps_id)
            except Exception:
                pass  # job may not exist in APScheduler

        # Remove cron job if exists
        try:
            if self.scheduler:
                self.scheduler.remove_job(f"cron_{job_id}")
        except Exception:
            pass

        return await job_store.cancel_job(job_id)

    # ---- APScheduler trigger helpers ----

    def _add_date_trigger(self, job_id: str, run_at: datetime, tag: str):
        """Schedule a one-shot DateTrigger."""
        aps_job_id = f"job_{job_id}_{tag}"
        self.scheduler.add_job(
            _aps_execute_job_wrapper,
            trigger=DateTrigger(run_date=run_at),
            id=aps_job_id,
            args=[job_id],
            replace_existing=True,
            name=f"Job {job_id} ({tag})"
        )

    def _add_prefetch_trigger(self, job_id: str, run_at: datetime):
        """Schedule a prefetch DateTrigger."""
        aps_job_id = f"job_{job_id}_prefetch"
        self.scheduler.add_job(
            _aps_execute_prefetch_wrapper,
            trigger=DateTrigger(run_date=run_at),
            id=aps_job_id,
            args=[job_id],
            replace_existing=True,
            name=f"Prefetch {job_id}"
        )

    def _add_cron_trigger(self, job_id: str, cron_expr: str):
        """Schedule a recurring CronTrigger from a cron expression."""
        parts = cron_expr.strip().split()
        
        # Standard 5-field cron: minute hour day month day_of_week
        cron_kwargs = {}
        if len(parts) >= 5:
            cron_kwargs = {
                "minute": parts[0],
                "hour": parts[1],
                "day": parts[2],
                "month": parts[3],
                "day_of_week": parts[4],
            }
        else:
            LOGGER.error(f"SCHEDULER: Invalid cron expression '{cron_expr}', using hourly default")
            cron_kwargs = {"minute": "0"}  # fallback: every hour

        aps_job_id = f"cron_{job_id}"
        self.scheduler.add_job(
            _aps_execute_job_wrapper,
            trigger=CronTrigger(**cron_kwargs),
            id=aps_job_id,
            args=[job_id],
            replace_existing=True,
            name=f"Cron {job_id}"
        )

    async def _rehydrate_jobs(self):
        """
        On startup, check for PENDING/READY jobs that may need
        APScheduler triggers re-registered (e.g., after a restart).
        """
        try:
            pending = await job_store.get_user_jobs(
                status_filter=["pending", "ready", "prefetching"],
                exclude_internal=False
            )
            rehydrated = 0
            for job in pending:
                job_id = job["_id"]
                job_type = job.get("job_type")
                trigger_at = job.get("trigger_at")
                prefetch_at = job.get("prefetch_at")
                cron_expr = job.get("cron_expression")

                if not trigger_at:
                    continue

                # Re-register triggers
                if job_type == JobType.CRON.value and cron_expr:
                    self._add_cron_trigger(job_id, cron_expr)
                elif trigger_at > datetime.now():
                    self._add_date_trigger(job_id, trigger_at, "main")

                if prefetch_at and prefetch_at > datetime.now():
                    self._add_prefetch_trigger(job_id, prefetch_at)

                rehydrated += 1

            if rehydrated:
                LOGGER.info(f"SCHEDULER: Rehydrated {rehydrated} jobs from database")
        except Exception as e:
            LOGGER.error(f"SCHEDULER: Rehydration failed (non-fatal): {e}")

    def add_email_cron(self, interval_seconds: int):
        """Register the email check as an APScheduler interval job."""
        from arcis.core.workflow_auto.auto_flow import run_autonomous_processing

        self.scheduler.add_job(
            _aps_async_wrapper,
            trigger="interval",
            seconds=interval_seconds,
            id="email_cron",
            args=[run_autonomous_processing],
            replace_existing=True,
            name="Email Processing Cron",
            max_instances=1,
            coalesce=True
        )
        LOGGER.info(f"SCHEDULER: Email cron registered (every {interval_seconds}s)")


# ---- APScheduler-compatible wrapper functions ----
# These are async functions natively awaited by APScheduler's AsyncIOScheduler.

async def _aps_execute_job_wrapper(job_id: str):
    """Async wrapper for execute_job."""
    await execute_job(job_id)


async def _aps_execute_prefetch_wrapper(job_id: str):
    """Async wrapper for execute_prefetch."""
    await execute_prefetch(job_id)


async def _aps_async_wrapper(async_func):
    """Generic async wrapper for any async function."""
    await async_func()


# Singleton
scheduler_service = SchedulerService()
