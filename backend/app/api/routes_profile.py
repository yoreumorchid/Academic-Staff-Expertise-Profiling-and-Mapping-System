"""UC-7 staff directory and comprehensive profile routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.profile_responses import expertise_link_to_out, publication_to_out
from app.api.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import Publication, User, UserExpertiseTag, UserRole
from app.db.session import get_session
from app.schemas import (
    StaffDirectoryEntry,
    StaffDirectoryPage,
    StaffProfileDetail,
    StaffSearchQuery,
)
from app.services.staff_search import search_staff as search_staff_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get(
    "/staff",
    response_model=StaffDirectoryPage,
    summary="UC-7 — Faculty Administrator browses or searches staff profiles.",
)
async def search_staff(
    query: StaffSearchQuery = Depends(),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> StaffDirectoryPage:
    if actor.role != UserRole.FACULTY_ADMINISTRATOR:
        raise ForbiddenError("Only administrators may browse the staff directory.")

    result = await search_staff_service(session, query)
    items = [
        StaffDirectoryEntry(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            department=user.department,
            tag_labels=[
                link.tag.canonical_label for link in user.expertise_links
            ],
        )
        for user in result.users
    ]
    return StaffDirectoryPage(
        items=items,
        total=result.total,
        department_count=result.department_count,
        tagged_count=result.tagged_count,
        page=query.page,
        page_size=query.page_size,
        total_pages=(result.total + query.page_size - 1) // query.page_size,
    )


@router.get(
    "/staff/{user_id}",
    response_model=StaffProfileDetail,
    summary="UC-7 — Render the comprehensive staff expertise profile.",
)
async def get_staff_profile(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> StaffProfileDetail:
    if actor.role != UserRole.FACULTY_ADMINISTRATOR and actor.id != user_id:
        raise ForbiddenError("You may only view your own profile.")
    user = await _load_full_profile(session, user_id)
    return StaffProfileDetail(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        department=user.department,
        tag_labels=[
            link.tag.canonical_label for link in user.expertise_links
        ],
        publications=[publication_to_out(item) for item in user.publications],
        expertise=[
            expertise_link_to_out(link) for link in user.expertise_links
        ],
    )


async def _load_full_profile(session: AsyncSession, user_id: UUID) -> User:
    stmt = (
        select(User)
        .where(
            User.id == user_id,
            or_(User.role == UserRole.ACADEMIC_STAFF, User.is_dual_role.is_(True)),
        )
        .options(
            selectinload(User.expertise_links).selectinload(UserExpertiseTag.tag),
            selectinload(User.publications).selectinload(Publication.abstract),
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise NotFoundError("Academic staff profile not found.")
    return user
