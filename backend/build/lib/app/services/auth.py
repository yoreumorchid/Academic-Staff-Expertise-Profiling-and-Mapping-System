"""Authentication and account-lifecycle services.

Implements:

* UC-1 — registration (creates a Pending account, optionally flags
  dual-role, persists ORCID linkage and administrator portfolio).
* UC-2 — Faculty Manager approval / rejection.
* UC-3 — credential verification with first-login sync trigger.
* UC-4 — password reset request, token consumption, in-session change.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailure,
)
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    verify_password,
)
from app.db.models import (
    AccountStatus,
    OrcidProfile,
    PasswordResetToken,
    Portfolio,
    User,
    UserRole,
)
from app.schemas import RegisterRequest
from app.services.notifications import NotificationService


class AuthService:
    """Coordinates auth flows against the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    async def _load_user_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(
                selectinload(User.portfolios),
                selectinload(User.orcid_profile),
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _load_user_by_id(self, user_id: UUID) -> User:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.portfolios),
                selectinload(User.orcid_profile),
            )
        )
        user = (await self._session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found.")
        return user

    # ------------------------------------------------------------------
    # UC-1 — registration
    # ------------------------------------------------------------------

    async def register(self, payload: RegisterRequest) -> User:
        normalized_email = payload.email.lower()
        existing = await self._load_user_by_email(normalized_email)
        if existing is not None:
            # UC-1 Exception: Email already exists.
            raise ConflictError("Email is already registered. Please log in instead.")

        is_dual_role = (
            payload.role == UserRole.FACULTY_ADMINISTRATOR and payload.orcid_id is not None
        )

        user = User(
            full_name=payload.full_name.strip(),
            email=normalized_email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            status=AccountStatus.PENDING,
            department=payload.department,
            is_dual_role=is_dual_role,
        )
        self._session.add(user)
        await self._session.flush()

        if payload.role == UserRole.FACULTY_ADMINISTRATOR and payload.portfolio is not None:
            self._session.add(
                Portfolio(user_id=user.id, portfolio_type=payload.portfolio)
            )

        if payload.orcid_id:
            self._session.add(
                OrcidProfile(user_id=user.id, orcid_id=payload.orcid_id)
            )

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError("Account could not be created due to a conflict.") from exc

        return await self._load_user_by_id(user.id)

    # ------------------------------------------------------------------
    # UC-2 — Faculty Manager authorization
    # ------------------------------------------------------------------

    async def list_pending(self) -> List[User]:
        stmt = (
            select(User)
            .where(User.status == AccountStatus.PENDING)
            .options(
                selectinload(User.portfolios),
                selectinload(User.orcid_profile),
            )
            .order_by(User.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def authorize(self, target_user_id: UUID, *, approve: bool) -> User | None:
        user = await self._load_user_by_id(target_user_id)
        if user.status != AccountStatus.PENDING:
            raise ValidationFailure("Only pending accounts can be authorized.")

        notifier = NotificationService(self._session)

        if approve:
            user.status = AccountStatus.ACTIVE
            await self._session.commit()
            await notifier.notify_registration_outcome(user, approved=True)
            await self._session.commit()
            return user

        # Rejection: capture the address for notification, then delete the
        # account so subsequent registrations may reuse the email.
        rejected_snapshot = User(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            password_hash="",
            role=user.role,
        )
        await notifier.notify_registration_outcome(rejected_snapshot, approved=False)
        await self._session.delete(user)
        await self._session.commit()
        return None

    # ------------------------------------------------------------------
    # UC-3 — login
    # ------------------------------------------------------------------

    async def authenticate(self, email: str, password: str) -> tuple[User, bool]:
        """Validate credentials and return (user, first_login_flag)."""
        user = await self._load_user_by_email(email.lower())
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")
        if user.status == AccountStatus.PENDING:
            raise ForbiddenError(
                "Your account is awaiting administrative approval."
            )
        if user.status != AccountStatus.ACTIVE:
            raise ForbiddenError("This account is not active.")

        first_login = not user.first_login_completed
        user.last_login_at = datetime.now(timezone.utc)
        user.first_login_completed = True
        await self._session.commit()
        return user, first_login

    def issue_token(self, user: User) -> str:
        claims = {
            "role": user.role.value,
            "portfolios": [p.portfolio_type.value for p in user.portfolios],
            "dual_role": user.is_dual_role,
        }
        return create_access_token(str(user.id), claims=claims)

    # ------------------------------------------------------------------
    # UC-4 — password reset
    # ------------------------------------------------------------------

    async def request_password_reset(self, email: str) -> None:
        user = await self._load_user_by_email(email.lower())
        if user is None:
            # UC-4 Exception: Email Not Found. The spec mandates an explicit
            # error message rather than silent success.
            raise NotFoundError("Email address not recognized.")

        token_value = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.password_reset_ttl_minutes
        )
        self._session.add(
            PasswordResetToken(
                user_id=user.id, token=token_value, expires_at=expires_at
            )
        )
        await self._session.commit()
        await NotificationService(self._session).notify_password_reset(user, token_value)
        await self._session.commit()

    async def consume_reset_token(self, token: str, new_password: str) -> None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token == token)
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None or record.consumed_at is not None:
            raise ValidationFailure("This reset link is no longer valid.")
        if record.expires_at < datetime.now(timezone.utc):
            # UC-4 Exception: Expired Token.
            raise ValidationFailure("This reset link has expired. Please request a new one.")

        user = await self._load_user_by_id(record.user_id)
        user.password_hash = hash_password(new_password)
        record.consumed_at = datetime.now(timezone.utc)
        await self._session.commit()

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        await self._session.commit()
