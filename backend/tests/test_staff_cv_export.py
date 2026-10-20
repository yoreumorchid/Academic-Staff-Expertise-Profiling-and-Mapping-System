"""Focused UC-18 administrator staff CV export regressions."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import routes_export
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import UserRole
from app.schemas import ExportSnapshotRequest


def _default_request() -> ExportSnapshotRequest:
    return ExportSnapshotRequest(format="pdf", use_defaults=True)


def test_academic_staff_cannot_export_another_staff_cv() -> None:
    actor = SimpleNamespace(role=UserRole.ACADEMIC_STAFF)

    with pytest.raises(ForbiddenError, match="Only administrators"):
        asyncio.run(
            routes_export.export_staff_snapshot(
                user_id=uuid4(),
                payload=_default_request(),
                session=object(),  # type: ignore[arg-type]
                actor=actor,  # type: ignore[arg-type]
            )
        )


def test_administrator_cannot_export_ineligible_target() -> None:
    class FakeSession:
        async def scalar(self, statement: object) -> None:
            return None

    actor = SimpleNamespace(role=UserRole.FACULTY_ADMINISTRATOR)

    with pytest.raises(NotFoundError, match="profile not found"):
        asyncio.run(
            routes_export.export_staff_snapshot(
                user_id=uuid4(),
                payload=_default_request(),
                session=FakeSession(),  # type: ignore[arg-type]
                actor=actor,  # type: ignore[arg-type]
            )
        )


def test_administrator_exports_target_with_default_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_id = uuid4()
    captured: dict[str, object] = {}

    class FakeSession:
        async def scalar(self, statement: object) -> object:
            return target_id

    class FakeExportService:
        def __init__(self, session: object) -> None:
            pass

        async def generate(
            self, *, user_id: object, request: ExportSnapshotRequest
        ) -> tuple[bytes, str, str]:
            captured["user_id"] = user_id
            captured["use_defaults"] = request.use_defaults
            return b"pdf", "application/pdf", "staff-snapshot.pdf"

    monkeypatch.setattr(routes_export, "ExportService", FakeExportService)
    actor = SimpleNamespace(role=UserRole.FACULTY_ADMINISTRATOR)
    response = asyncio.run(
        routes_export.export_staff_snapshot(
            user_id=target_id,
            payload=_default_request(),
            session=FakeSession(),  # type: ignore[arg-type]
            actor=actor,  # type: ignore[arg-type]
        )
    )

    assert response.body == b"pdf"
    assert captured == {"user_id": target_id, "use_defaults": True}
