from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from arcis.core.scheduler.job_store import job_store
from arcis.core.scheduler.scheduler_service import scheduler_service

scheduler_router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


class JobResponse(BaseModel):
    id: str = Field(..., alias="_id")
    job_type: str
    title: str
    description: str = ""
    trigger_at: datetime
    cron_expression: Optional[str] = None
    prefetch_at: Optional[datetime] = None
    calendar_item_id: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        populate_by_name = True


class CancelResponse(BaseModel):
    status: str
    message: str


@scheduler_router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[str] = None
):
    """List all scheduled jobs. Optionally filter by status."""
    status_filter = [status] if status else None
    jobs = await job_store.get_user_jobs(status_filter=status_filter)
    return jobs


@scheduler_router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get details of a specific job."""
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@scheduler_router.post("/jobs/{job_id}/cancel", response_model=CancelResponse)
async def cancel_job(job_id: str):
    """Cancel a scheduled job."""
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job is already {job['status']}")

    success = await scheduler_service.cancel_job(job_id)
    if success:
        return {"status": "cancelled", "message": f"Job {job_id} cancelled successfully"}
    raise HTTPException(status_code=500, detail="Failed to cancel job")


@scheduler_router.delete("/jobs/{job_id}", response_model=CancelResponse)
async def delete_job(job_id: str):
    """Permanently delete a job."""
    success = await job_store.delete_job(job_id)
    if success:
        return {"status": "deleted", "message": f"Job {job_id} deleted"}
    raise HTTPException(status_code=404, detail="Job not found")
