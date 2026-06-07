"""Authentication endpoints — UC-1, UC-3, UC-4."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import SyncTrigger, User
from app.db.session import SessionLocal, get_session
from app.schemas import (
    ChangePasswordRequest,
    CurrentUserOut,
    ForgotPasswordRequest,
    LoginRequest,
    PortfolioOut,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth import AuthService
from app.services.harvest import HarvestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_current_user_out(user: User) -> CurrentUserOut:
    return CurrentUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        status=user.status,
        department=user.department,
        is_dual_role=user.is_dual_role,
        portfolios=[PortfolioOut.model_validate(p) for p in user.portfolios],
        orcid_id=user.orcid_profile.orcid_id if user.orcid_profile else None,
    )


async def _kick_off_first_login_sync(user_id: UUID) -> None:
    """UC-3 alt flows — fire-and-forget harvest after first login."""
    async with SessionLocal() as session:
        try:
            await HarvestService(session).run_for_user(
                user_id, trigger=SyncTrigger.FIRST_LOGIN
            )
        except Exception:  # noqa: BLE001 — log and swallow; never block login.
            logger.exception("First-login harvest failed for user %s", user_id)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="UC-1 — Register a new account in Pending state.",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    service = AuthService(session)
    user = await service.register(payload)
    return RegisterResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="UC-3 — Authenticate and obtain an access token.",
)
async def login(
    payload: LoginRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    service = AuthService(session)
    user, first_login = await service.authenticate(payload.email, payload.password)
    # UC-3 alt flows: first-login (and dual-role first-login) automatically
    # trigger an ORCID/OpenAlex sync. The harvest is scheduled in the
    # background so the login response remains fast.
    # Guard: check orcid_id on the profile row — the relationship object may
    # not be loaded into the session even when the row exists.
    has_orcid = (
        user.orcid_profile is not None and bool(user.orcid_profile.orcid_id)
    )
    if first_login and has_orcid:
        background.add_task(_kick_off_first_login_sync, user.id)
    token = service.issue_token(user)
    return TokenResponse(access_token=token, user=_to_current_user_out(user))


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="UC-4 — Request a password reset link.",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await AuthService(session).request_password_reset(payload.email)
    return {"status": "reset_email_sent"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-4 — Consume a reset token to set a new password.",
)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    await AuthService(session).consume_reset_token(payload.token, payload.new_password)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-4 Alternative — Change password from within the session.",
)
async def change_password(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    await AuthService(session).change_password(
        user, payload.current_password, payload.new_password
    )


@router.get(
    "/me",
    response_model=CurrentUserOut,
    summary="UC-6 — Resolve the authenticated user's role and portfolios.",
)
async def me(user: User = Depends(get_current_user)) -> CurrentUserOut:
    return _to_current_user_out(user)
