"""Shared FastAPI dependencies for authentication and role enforcement."""
from __future__ import annotations

from typing import Iterable
from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import PortfolioType, User, UserRole
from app.db.session import get_session


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the authenticated ``User`` from the ``Authorization`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid access token.") from exc

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Token subject is invalid.") from exc

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.portfolios),
            selectinload(User.orcid_profile),
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("Account no longer exists.")
    return user


def require_role(*roles: UserRole):
    """Dependency factory enforcing one or more high-level account roles."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("This action requires a different account role.")
        return user

    return _checker


def require_portfolio(*allowed: PortfolioType):
    """Dependency factory enforcing UC-6 portfolio permissions."""

    allowed_set = set(allowed)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        held = {p.portfolio_type for p in user.portfolios}
        if not (allowed_set & held):
            raise ForbiddenError(
                "Your portfolio does not grant access to this module."
            )
        return user

    return _checker


def has_any_portfolio(user: User, candidates: Iterable[PortfolioType]) -> bool:
    held = {p.portfolio_type for p in user.portfolios}
    return any(c in held for c in candidates)
