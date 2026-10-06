"""Application service that persists and publishes synchronization jobs."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.models import SyncJob, SyncJobStatus, SyncTrigger
from app.services.harvest import HarvestService
from app.worker import celery_app


async def ensure_user_sync_inactive(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    """Reject profile mutations that would race an active sync job."""
    stmt = (
        select(SyncJob.id)
        .where(SyncJob.user_id == user_id)
        .where(SyncJob.status.in_((SyncJobStatus.QUEUED, SyncJobStatus.RUNNING)))
        .limit(1)
    )
    active_job_id = (await session.execute(stmt)).scalar_one_or_none()
    if active_job_id is not None:
        raise ConflictError(
            "Your expertise profile is currently synchronizing. "
            "Please wait until it finishes before editing publications or tags.",
            details={"job_id": str(active_job_id)},
        )


async def enqueue_user_sync(
    session: AsyncSession,
    user_id: UUID,
    *,
    trigger: SyncTrigger,
) -> SyncJob:
    """Persist a queued job, then publish its identifier to Redis."""
    job = await HarvestService(session).create_job(user_id, trigger=trigger)
    try:
        await asyncio.to_thread(
            celery_app.send_task,
            "sync.run_job",
            args=[str(job.id)],
        )
    except Exception as exc:  # Broker unavailable: retain an auditable failed row.
        job.status = SyncJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = "Could not publish the job to the task queue."
        await session.commit()
        raise ExternalServiceError(
            "The synchronization queue is currently unavailable."
        ) from exc
    return job
