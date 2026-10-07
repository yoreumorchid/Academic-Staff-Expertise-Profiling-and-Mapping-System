"""SQL-backed staff directory search for UC-7.

The directory is faculty-wide for every Faculty Administrator.  Department is
therefore a search filter, not an authorization boundary: cross-department
expertise discovery is an intentional product requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import ValidationFailure
from app.db.models import (
    AccountStatus,
    ExpertiseTag,
    Publication,
    User,
    UserExpertiseTag,
    UserRole,
)
from app.schemas import StaffSearchQuery


@dataclass(frozen=True)
class StaffSearchResult:
    users: list[User]
    total: int
    department_count: int
    tagged_count: int


def _contains_pattern(value: str) -> str:
    """Return an escaped ILIKE substring pattern.

    ``%`` and ``_`` remain literal user input, matching the old Python
    substring behavior instead of becoming SQL wildcards.
    """

    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def build_staff_search_filters(query: StaffSearchQuery) -> Sequence[ColumnElement[bool]]:
    """Build the complete faculty-wide visibility and search predicate set."""

    filters: list[ColumnElement[bool]] = [
        or_(
            User.role == UserRole.ACADEMIC_STAFF,
            User.is_dual_role.is_(True),
        ),
        User.status == AccountStatus.ACTIVE,
    ]

    if query.department:
        filters.append(
            User.department.ilike(_contains_pattern(query.department), escape="\\")
        )

    if query.q:
        keyword = query.q.strip()
        if not keyword:
            raise ValidationFailure("Provide a search term to query staff profiles.")
        pattern = _contains_pattern(keyword)
        name_match = User.full_name.ilike(pattern, escape="\\")
        department_match = User.department.ilike(pattern, escape="\\")
        expertise_match = User.expertise_links.any(
            UserExpertiseTag.tag.has(
                ExpertiseTag.canonical_label.ilike(pattern, escape="\\")
            )
        )
        publication_match = User.publications.any(
            or_(
                Publication.title.ilike(pattern, escape="\\"),
                Publication.venue.ilike(pattern, escape="\\"),
                Publication.doi.ilike(pattern, escape="\\"),
            )
        )
        category = query.category or "name"
        category_filter = {
            "name": name_match,
            "department": department_match,
            "expertise": expertise_match,
            "publication": publication_match,
            "all": or_(
                name_match,
                department_match,
                expertise_match,
                publication_match,
            ),
        }
        filters.append(category_filter[category])

    if query.tag_label:
        tag_pattern = _contains_pattern(query.tag_label.strip())
        filters.append(
            User.expertise_links.any(
                UserExpertiseTag.tag.has(
                    ExpertiseTag.canonical_label.ilike(tag_pattern, escape="\\")
                )
            )
        )

    return filters


async def search_staff(
    session: AsyncSession,
    query: StaffSearchQuery,
) -> StaffSearchResult:
    """Count and fetch one stable page without loading unmatched profiles."""

    filters = build_staff_search_filters(query)
    count_stmt = (
        select(
            func.count(User.id),
            func.count(func.distinct(User.department)),
            func.count(User.id).filter(User.expertise_links.any()),
        )
        .select_from(User)
        .where(*filters)
    )
    total, department_count, tagged_count = (await session.execute(count_stmt)).one()

    stmt = (
        select(User)
        .where(*filters)
        .options(
            selectinload(User.expertise_links).selectinload(UserExpertiseTag.tag)
        )
        .order_by(func.lower(User.full_name), User.id)
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    users = list((await session.execute(stmt)).scalars().all())
    return StaffSearchResult(
        users=users,
        total=int(total),
        department_count=int(department_count),
        tagged_count=int(tagged_count),
    )
