"""FastAPI application factory.

Run with::

    uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import SessionLocal
from app.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)

_log = logging.getLogger(__name__)


async def _clean_orphaned_sync_jobs() -> None:
    """Mark any RUNNING sync_jobs from a previous process as FAILED.

    When the server restarts (or uvicorn --reload triggers), any
    sync_jobs still flagged RUNNING are orphans — the process that
    created them is dead and can never finish them.  Without this
    cleanup the concurrent-sync guard in ``HarvestService.run_for_user``
    permanently blocks that user from running another sync.
    """
    from app.db.models import SyncJob, SyncJobStatus
    from sqlalchemy import select, update

    async with SessionLocal() as session:
        orphan_stmt = (
            select(SyncJob.id)
            .where(SyncJob.status == SyncJobStatus.RUNNING)
        )
        orphan_ids = (await session.execute(orphan_stmt)).scalars().all()
        if orphan_ids:
            _log.warning(
                "Cleaning up %d orphaned RUNNING sync job(s): %s",
                len(orphan_ids),
                [str(oid) for oid in orphan_ids],
            )
            await session.execute(
                update(SyncJob)
                .where(SyncJob.id.in_(orphan_ids))
                .values(
                    status=SyncJobStatus.FAILED,
                    error_message="Orphaned by server restart",
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ExpertiseInsight API",
        version="0.1.0",
        description=(
            "Backend service implementing the use cases UC-1 through UC-18 "
            "specified in use_cases.md."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.on_event("startup")
    async def _on_startup() -> None:
        # Clean any orphaned sync jobs from previous process runs.
        await _clean_orphaned_sync_jobs()
        # UC-12 alt flow — quarterly automated synchronization.
        start_scheduler()

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        shutdown_scheduler()

    @app.get("/health", tags=["meta"], summary="Liveness probe.")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()