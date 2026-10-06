"""Critical queue behavior: persist first, then publish a small job id."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ExternalServiceError
from app.db.models import SyncJobStatus, SyncTrigger
from app.services import sync_queue


def test_enqueue_marks_job_failed_when_redis_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = SimpleNamespace(
        id=uuid4(),
        status=SyncJobStatus.QUEUED,
        finished_at=None,
        error_message=None,
    )

    async def fake_create_job(self, user_id, *, trigger):
        return job

    def fail_publish(*args, **kwargs):
        raise ConnectionError("Redis is offline")

    class FakeSession:
        committed = False

        async def commit(self):
            self.committed = True

    session = FakeSession()
    monkeypatch.setattr(sync_queue.HarvestService, "create_job", fake_create_job)
    monkeypatch.setattr(sync_queue.celery_app, "send_task", fail_publish)

    with pytest.raises(ExternalServiceError):
        asyncio.run(
            sync_queue.enqueue_user_sync(
                session,
                uuid4(),
                trigger=SyncTrigger.MANUAL,
            )
        )

    assert session.committed is True
    assert job.status == SyncJobStatus.FAILED
    assert job.finished_at is not None
    assert "task queue" in job.error_message
