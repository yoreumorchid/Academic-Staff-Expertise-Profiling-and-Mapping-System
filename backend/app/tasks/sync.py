"""Celery tasks for expertise synchronization."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.exceptions import ConflictError, ExternalServiceError
from app.db.models import SyncTrigger
from app.db.session import SessionLocal, engine
from app.services.harvest import HarvestService, list_users_for_quarterly_sync
from app.worker import celery_app

logger = logging.getLogger(__name__)


async def _dispose_engine() -> None:
    # Celery invokes each task through asyncio.run(), which creates a new event
    # loop. Dispose pooled asyncpg connections before that loop is closed.
    await engine.dispose()


async def _run_job(job_id: str) -> None:
    try:
        async with SessionLocal() as session:
            await HarvestService(session).run_job(UUID(job_id))
    finally:
        await _dispose_engine()


@celery_app.task(bind=True, name="sync.run_job", max_retries=2)
def run_sync_job(self, job_id: str) -> None:
    """Execute one durable sync job and retry transient provider failures."""
    try:
        asyncio.run(_run_job(job_id))
    except ExternalServiceError as exc:
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


async def _enqueue_quarterly_jobs() -> int:
    from app.services.sync_queue import enqueue_user_sync

    queued = 0
    try:
        async with SessionLocal() as session:
            users = await list_users_for_quarterly_sync(session)
            for user in users:
                try:
                    await enqueue_user_sync(
                        session,
                        user.id,
                        trigger=SyncTrigger.QUARTERLY,
                    )
                    queued += 1
                except ConflictError:
                    logger.info("Skipping quarterly sync for busy user %s", user.id)
                except Exception:  # Keep one user failure from stopping the batch.
                    logger.exception("Could not queue quarterly sync for %s", user.id)
    finally:
        await _dispose_engine()
    return queued


@celery_app.task(name="sync.enqueue_quarterly")
def enqueue_quarterly_syncs() -> int:
    """Queue all ORCID-linked users at the start of each quarter."""
    return asyncio.run(_enqueue_quarterly_jobs())
