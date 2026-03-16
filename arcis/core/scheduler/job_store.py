from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId

from arcis.database.mongo.connection import mongo, COLLECTIONS
from arcis.models.scheduler.job_models import ScheduledJob, JobStatus
from arcis.logger import LOGGER


class JobStore:
    """Async CRUD operations for the scheduled_jobs collection."""

    @property
    def collection(self):
        return mongo.db[COLLECTIONS['scheduled_jobs']]


    async def create_job(self, job: ScheduledJob) -> str:
        """Insert a new job and return its string ID."""
        data = job.model_dump()
        result = await self.collection.insert_one(data)
        job_id = str(result.inserted_id)
        LOGGER.info(f"JOBSTORE: Created job {job_id} — [{job.job_type.value}] {job.title}")
        return job_id


    async def get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve a single job by ID."""
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return None
        doc = await self.collection.find_one({"_id": oid})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc


    async def get_user_jobs(
        self,
        status_filter: list[str] | None = None,
        exclude_internal: bool = True
    ) -> list[dict]:
        """
        List jobs visible to the user.
        By default hides internal sub-jobs (those with a parent_job_id).
        """
        query = {}
        if status_filter:
            query["status"] = {"$in": status_filter}
        if exclude_internal:
            query["parent_job_id"] = None
        
        cursor = self.collection.find(query).sort("trigger_at", 1)
        jobs = await cursor.to_list(length=200)
        for j in jobs:
            j["_id"] = str(j["_id"])
        return jobs


    async def get_pending_jobs(self) -> list[dict]:
        """Jobs whose trigger_at has passed and are still pending/ready."""
        now = datetime.now()
        cursor = self.collection.find({
            "status": {"$in": [JobStatus.PENDING.value, JobStatus.READY.value]},
            "trigger_at": {"$lte": now}
        }).sort("trigger_at", 1)
        jobs = await cursor.to_list(length=100)
        for j in jobs:
            j["_id"] = str(j["_id"])
        return jobs


    async def get_jobs_needing_prefetch(self) -> list[dict]:
        """Jobs whose prefetch_at has passed but haven't been prefetched yet."""
        now = datetime.now()
        cursor = self.collection.find({
            "status": JobStatus.PENDING.value,
            "prefetch_at": {"$ne": None, "$lte": now}
        }).sort("prefetch_at", 1)
        jobs = await cursor.to_list(length=50)
        for j in jobs:
            j["_id"] = str(j["_id"])
        return jobs


    async def update_job(self, job_id: str, updates: dict) -> bool:
        """Update specific fields on a job."""
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return False
        result = await self.collection.update_one(
            {"_id": oid},
            {"$set": updates}
        )
        return result.modified_count > 0


    async def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> bool:
        """Convenience: update job status and optionally set error."""
        updates = {"status": status.value}
        if status == JobStatus.COMPLETED:
            updates["completed_at"] = datetime.now()
        if error:
            updates["error"] = error
        return await self.update_job(job_id, updates)


    async def store_context(self, job_id: str, context: dict) -> bool:
        """Store prefetched context on a job and mark it READY."""
        return await self.update_job(job_id, {
            "context": context,
            "status": JobStatus.READY.value
        })


    async def cancel_job(self, job_id: str) -> bool:
        """Soft-cancel a job (sets status to CANCELLED)."""
        return await self.set_status(job_id, JobStatus.CANCELLED)


    async def delete_job(self, job_id: str) -> bool:
        """Hard-delete a job from the collection."""
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0


job_store = JobStore()
