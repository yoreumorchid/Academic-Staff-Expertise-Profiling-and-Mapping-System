"""UC-12 — Manual and quarterly expertise synchronization."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import ForbiddenError
from app.db.models import SyncJob, SyncJobStatus, SyncTrigger, User, UserRole
from app.db.session import get_session
from app.schemas import SyncJobOut, SyncStatusOut
from app.services.harvest import HarvestService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post(
    "/me",
    response_model=SyncJobOut,
    summary="UC-12 — Academic staff manually trigger a sync for themselves.",
)
async def trigger_self_sync(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncJobOut:
    job = await HarvestService(session).run_for_user(
        actor.id, trigger=SyncTrigger.MANUAL
    )
    return SyncJobOut.model_validate(job)


@router.post(
    "/users/{target_user_id}",
    response_model=SyncJobOut,
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
    job = await HarvestService(session).run_for_user(
        target_user_id, trigger=SyncTrigger.MANUAL
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
    "/status",
    response_model=SyncStatusOut,
    summary="UC-12 — Lightweight poller for whether the actor has a sync running.",
)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> SyncStatusOut:
    """Return whether the calling user currently has a RUNNING sync job.

    Polled every few seconds by the frontend so a global “Sync in progress…”
    modal can appear regardless of whether the sync was kicked off by
    first-login, manual button, or a Faculty Administrator trigger.
    """
    stmt = (
        select(SyncJob)
        .where(SyncJob.user_id == actor.id)
        .where(SyncJob.status == SyncJobStatus.RUNNING)
        .order_by(SyncJob.created_at.desc())
        .limit(1)
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if job is None:
        return SyncStatusOut(running=False)
    return SyncStatusOut(
        running=True,
        trigger=job.trigger,
        started_at=job.started_at,
    )
