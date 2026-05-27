"""UC-2 — Faculty Manager registration review endpoints."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_portfolio
from app.db.models import PortfolioType, User
from app.db.session import get_session
from app.schemas import AuthorizeRequest, PendingRegistrationOut, PortfolioOut
from app.services.auth import AuthService

router = APIRouter(prefix="/admin/registrations", tags=["admin"])


def _to_pending(user: User) -> PendingRegistrationOut:
    return PendingRegistrationOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department,
        portfolios=[PortfolioOut.model_validate(p) for p in user.portfolios],
        orcid_id=user.orcid_profile.orcid_id if user.orcid_profile else None,
        created_at=user.created_at,
    )


@router.get(
    "",
    response_model=List[PendingRegistrationOut],
    summary="UC-2 — List pending registration requests.",
)
async def list_pending(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_portfolio(PortfolioType.FACULTY_MANAGER)),
) -> List[PendingRegistrationOut]:
    users = await AuthService(session).list_pending()
    return [_to_pending(u) for u in users]


@router.post(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-2 — Approve or reject a pending registration.",
)
async def authorize_registration(
    user_id: UUID,
    payload: AuthorizeRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_portfolio(PortfolioType.FACULTY_MANAGER)),
) -> None:
    await AuthService(session).authorize(user_id, approve=payload.approve)
