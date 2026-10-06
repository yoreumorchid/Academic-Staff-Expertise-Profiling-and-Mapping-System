"""Critical FR-014 behavior: first login triggers expertise synchronization."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import routes_auth
from app.db.models import AccountStatus, UserRole
from app.schemas import LoginRequest


@pytest.mark.parametrize(
    ("first_login", "has_orcid", "expected_syncs"),
    [
        (True, True, 1),
        (False, True, 0),
        (True, False, 0),
    ],
)
def test_first_login_sync_trigger(
    monkeypatch: pytest.MonkeyPatch,
    first_login: bool,
    has_orcid: bool,
    expected_syncs: int,
) -> None:
    user_id = uuid4()
    user = SimpleNamespace(
        id=user_id,
        full_name="TEST USER",
        email="test.user@um.edu.my",
        role=UserRole.ACADEMIC_STAFF,
        status=AccountStatus.ACTIVE,
        department="Computer Science",
        is_dual_role=False,
        portfolios=[],
        orcid_profile=(
            SimpleNamespace(orcid_id="0000-0002-1825-0097")
            if has_orcid
            else None
        ),
    )

    class FakeAuthService:
        def __init__(self, session: object) -> None:
            self.session = session

        async def authenticate(self, email: str, password: str):
            return user, first_login

        def issue_token(self, authenticated_user: object) -> str:
            return "test-token"

    triggered_user_ids = []
    job_id = uuid4()

    async def fake_enqueue(session, triggered_user_id, *, trigger):
        triggered_user_ids.append(triggered_user_id)
        return SimpleNamespace(id=job_id)

    monkeypatch.setattr(routes_auth, "AuthService", FakeAuthService)
    monkeypatch.setattr(
        routes_auth,
        "enqueue_user_sync",
        fake_enqueue,
    )

    response = asyncio.run(
        routes_auth.login(
            LoginRequest(email=user.email, password="TestPassword1!"),
            session=object(),
        )
    )

    assert response.access_token == "test-token"
    assert triggered_user_ids == ([user_id] if expected_syncs else [])
    assert response.sync_job_id == (job_id if expected_syncs else None)
