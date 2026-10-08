"""Focused ARCH-01 regressions for route contracts and mapping PDF export."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import routes_profile
from app.core.exceptions import NotFoundError
from app.db.models import SpecificationType
from app.main import create_app
from app.services.mapping_export import render_mapping_report_pdf


def test_profile_and_mapping_route_contracts_are_unchanged() -> None:
    app = create_app()
    actual = {
        (method, route.path)
        for route in app.routes
        for method in (route.methods or set())
        if route.path.startswith(("/api/v1/profile", "/api/v1/mapping"))
    }

    assert actual == {
        ("GET", "/api/v1/profile/staff"),
        ("GET", "/api/v1/profile/staff/{user_id}"),
        ("GET", "/api/v1/profile/publications"),
        ("POST", "/api/v1/profile/publications/{publication_id}/abstract"),
        ("POST", "/api/v1/profile/publications/{publication_id}/abstract/upload"),
        ("GET", "/api/v1/profile/background"),
        ("POST", "/api/v1/profile/background"),
        ("PUT", "/api/v1/profile/background/{record_id}"),
        ("DELETE", "/api/v1/profile/background/{record_id}"),
        ("GET", "/api/v1/profile/background/template"),
        ("POST", "/api/v1/profile/background/upload"),
        ("GET", "/api/v1/profile/expertise"),
        ("POST", "/api/v1/profile/expertise/refine"),
        ("POST", "/api/v1/mapping/specs"),
        ("POST", "/api/v1/mapping/specs/upload"),
        ("POST", "/api/v1/mapping/specs/{spec_id}/match"),
        ("GET", "/api/v1/mapping/specs"),
        ("DELETE", "/api/v1/mapping/specs/{spec_id}"),
        ("GET", "/api/v1/mapping/specs/{spec_id}/export"),
        ("GET", "/api/v1/mapping/reports/{report_id}"),
    }


def test_mapping_pdf_renderer_still_produces_a_pdf() -> None:
    report = SimpleNamespace(
        spec=SimpleNamespace(
            title="Software Engineering",
            spec_type=SpecificationType.COURSE,
            raw_text="A course specification covering software architecture and testing.",
        ),
        created_at=datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc),
        entries=[
            SimpleNamespace(
                rank=1,
                user_id=uuid4(),
                cosine_score=0.9,
                spreading_score=0.5,
                combined_score=0.78,
            )
        ],
        summary="The strongest match combines direct and related expertise.",
    )

    content = asyncio.run(render_mapping_report_pdf(report))  # type: ignore[arg-type]

    assert content.startswith(b"%PDF-")
    assert len(content) > 1_000


def test_staff_profile_loader_builds_its_role_scope_query() -> None:
    class Result:
        def scalar_one_or_none(self) -> None:
            return None

    class Session:
        async def execute(self, statement: object) -> Result:
            return Result()

    with pytest.raises(NotFoundError, match="profile not found"):
        asyncio.run(
            routes_profile._load_full_profile(  # noqa: SLF001
                Session(),  # type: ignore[arg-type]
                uuid4(),
            )
        )
