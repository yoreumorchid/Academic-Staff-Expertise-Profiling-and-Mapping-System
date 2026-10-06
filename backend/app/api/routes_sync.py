"""UC-12 — Manual and quarterly expertise synchronization."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import SyncJob, SyncJobStatus, SyncTrigger, User, UserRole
from app.db.session import get_session
from app.schemas import SyncJobOut, SyncStatusOut
from app.services.sync_queue import enqueue_user_sync

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post(
    "/me",
    response_model=SyncJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="UC-12 — Academic staff manually trigger a sync for themselves.",
)
async def trigger_self_sync(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncJobOut:
    job = await enqueue_user_sync(
        session, actor.id, trigger=SyncTrigger.MANUAL
    )
    return SyncJobOut.model_validate(job)


@router.post(
    "/users/{target_user_id}",
    response_model=SyncJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="UC-12 — Faculty Administrator triggers a sync for any staff member.",
)
async def trigger_admin_sync(
    target_user_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncJobOut:
    if actor.role != UserRole.FACULTY_ADMINISTRATOR:
        raise ForbiddenError(
            "Only Faculty Administrators may trigger syncs for other users."
        )
    job = await enqueue_user_sync(
        session, target_user_id, trigger=SyncTrigger.MANUAL
    )
    return SyncJobOut.model_validate(job)


@router.get(
    "/jobs",
    response_model=List[SyncJobOut],
    summary="UC-12 — List recent sync jobs for the actor (or all, for admins).",
)
async def list_sync_jobs(
    user_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[SyncJobOut]:
    stmt = select(SyncJob).order_by(SyncJob.created_at.desc()).limit(50)
    if actor.role == UserRole.FACULTY_ADMINISTRATOR:
        if user_id is not None:
            stmt = stmt.where(SyncJob.user_id == user_id)
    else:
        stmt = stmt.where(SyncJob.user_id == actor.id)
    rows = (await session.execute(stmt)).scalars().all()
    return [SyncJobOut.model_validate(row) for row in rows]


@router.get(
    "/jobs/{job_id}",
    response_model=SyncJobOut,
    summary="UC-12 - Read one synchronization job for progress polling.",
)
async def get_sync_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncJobOut:
    job = await session.get(SyncJob, job_id)
    if job is None:
        raise NotFoundError("Sync job not found.")
    if actor.role != UserRole.FACULTY_ADMINISTRATOR and job.user_id != actor.id:
        raise ForbiddenError("You may only view your own synchronization jobs.")
    return SyncJobOut.model_validate(job)


@router.get(
    "/status",
    response_model=SyncStatusOut,
    summary="UC-12 — Return the actor's latest synchronization status.",
)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncStatusOut:
    """Return the latest job, including terminal state and result counts."""
    stmt = (
        select(SyncJob)
        .where(SyncJob.user_id == actor.id)
        .order_by(SyncJob.created_at.desc())
        .limit(1)
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if job is None:
        return SyncStatusOut(active=False)
    active = job.status in (SyncJobStatus.QUEUED, SyncJobStatus.RUNNING)
    return SyncStatusOut(
        active=active,
        job_id=job.id,
        status=job.status,
        progress_stage=job.progress_stage,
        trigger=job.trigger,
        started_at=job.started_at,
        finished_at=job.finished_at,
        publications_added=job.publications_added,
        tags_added=job.tags_added,
        error_message=job.error_message,
    )
