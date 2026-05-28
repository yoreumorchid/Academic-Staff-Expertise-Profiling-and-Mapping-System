"""APScheduler-backed quarterly synchronization (UC-12 alt flow).

The scheduler is started at application startup and runs once every 90
days. It iterates every active user with an ORCID profile and triggers
the same harvest pipeline used by the manual endpoint. Failures are
logged per-user but never crash the scheduler thread.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.models import SyncTrigger
from app.db.session import SessionLocal
from app.services.harvest import HarvestService, list_users_for_quarterly_sync

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _quarterly_job() -> None:
    """Iterate every ORCID-linked user and run a sync."""
    async with SessionLocal() as session:
        users = await list_users_for_quarterly_sync(session)
    logger.info("Quarterly sync starting for %d users", len(users))

    for user in users:
        async with SessionLocal() as session:
            try:
                await HarvestService(session).run_for_user(
                    user.id, trigger=SyncTrigger.QUARTERLY
                )
            except Exception:  # noqa: BLE001 — log and continue.
                logger.exception("Quarterly sync failed for user %s", user.id)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    # Every 90 days, fire at 02:00 server time.
    _scheduler.add_job(
        _quarterly_job,
        trigger="interval",
        days=90,
        id="expertise_quarterly_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Quarterly sync scheduler started.")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
