from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class JobType(str, Enum):
    REMINDER = "reminder"
    TODO = "todo"
    EVENT = "event"
    CRON = "cron"


class JobStatus(str, Enum):
    PENDING = "pending"
    PREFETCHING = "prefetching"
    READY = "ready"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledJob(BaseModel):
    """A scheduled job with metadata for the scheduler system."""

    job_type: JobType
    title: str
    description: str = ""

    # Timing
    trigger_at: datetime = Field(description="When the main action fires")
    cron_expression: Optional[str] = Field(
        default=None,
        description="Cron expression for recurring jobs (e.g. '0 9 * * 1' for every Monday 9am)"
    )
    prefetch_at: Optional[datetime] = Field(
        default=None,
        description="When to start context gathering (before trigger_at)"
    )

    # Relationships
    parent_job_id: Optional[str] = Field(
        default=None,
        description="ID of the parent job if this is an internal sub-job"
    )
    calendar_item_id: Optional[str] = Field(
        default=None,
        description="Linked calendar_events entry ID"
    )

    # Execution data
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Prefetched context (web results, memory, files)"
    )
    notification_message: str = Field(
        default="",
        description="Custom notification message to send when triggered"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="LangGraph thread ID for manual_flow resumption"
    )

    # Status tracking
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class SchedulerParseResult(BaseModel):
    """LLM structured output for parsing scheduling intent from natural language."""

    job_type: JobType = Field(description="Type of job to create")
    title: str = Field(description="Short title for the job")
    description: str = Field(
        default="",
        description="Detailed description of what needs to be done"
    )
    trigger_at: datetime = Field(
        description="ISO 8601 datetime when the job should trigger"
    )
    cron_expression: Optional[str] = Field(
        default=None,
        description="Cron expression for recurring jobs. Only set when job_type is 'cron'"
    )
    needs_context_prefetch: bool = Field(
        default=False,
        description="Whether this job needs context gathering before triggering (e.g., web search, file lookup)"
    )
    prefetch_queries: list[str] = Field(
        default_factory=list,
        description="Search queries to use during context prefetch. Only relevant when needs_context_prefetch=True"
    )
    notification_message: str = Field(
        default="",
        description="Custom notification text. If empty, title will be used"
    )
