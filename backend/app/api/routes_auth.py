"""Authentication endpoints — UC-1, UC-3, UC-4."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
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
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    service = AuthService(session)
    user, first_login = await service.authenticate(payload.email, payload.password)
    # UC-3 Alternative Flows (first-login sync) are enqueued by the sync
    # service in a subsequent build phase. The boolean is exposed via the
    # /me endpoint so the frontend can surface a "Synchronizing" toast.
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
