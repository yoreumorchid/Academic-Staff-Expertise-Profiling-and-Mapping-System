"""Focused PERF-01 regressions for SQL staff search and pagination."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.api import routes_profile
from app.core.exceptions import ForbiddenError
from app.db.models import User, UserRole
from app.schemas import StaffSearchQuery
from app.services.staff_search import (
    StaffSearchResult,
    build_staff_search_filters,
    search_staff,
)


def _sql(statement: object) -> str:
    return str(
        statement.compile(  # type: ignore[union-attr]
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()


@pytest.mark.parametrize(
    ("category", "expected_table", "excluded_table"),
    [
        ("name", "users.full_name", "publications"),
        ("department", "users.department", "publications"),
        ("expertise", "expertise_tags", "publications"),
        ("publication", "publications", "expertise_tags"),
    ],
)
def test_category_filters_are_applied_in_sql(
    category: str,
    expected_table: str,
    excluded_table: str,
) -> None:
    query = StaffSearchQuery(q="software", category=category)
    statement = select(User.id).where(*build_staff_search_filters(query))
    sql = _sql(statement)

    assert expected_table in sql
    assert excluded_table not in sql
    assert "users.role" in sql
    assert "academic_staff" in sql
    assert "users.is_dual_role is true" in sql
    assert "users.status" in sql
    # Faculty-wide visibility is deliberate: an administrator's department is
    # never injected as an authorization predicate.
    assert "actor" not in sql


def test_all_category_searches_every_supported_field_in_sql() -> None:
    query = StaffSearchQuery(q="engineering", category="all")
    sql = _sql(select(User.id).where(*build_staff_search_filters(query)))

    assert "users.full_name" in sql
    assert "users.department" in sql
    assert "expertise_tags" in sql
    assert "publications" in sql


def test_page_boundaries_become_limit_and_offset() -> None:
    class AggregateResult:
        def one(self) -> tuple[int, int, int]:
            return (21, 4, 18)

    class ScalarRows:
        def all(self) -> list[object]:
            return []

    class PageResult:
        def scalars(self) -> ScalarRows:
            return ScalarRows()

    class FakeSession:
        def __init__(self) -> None:
            self.statements: list[object] = []

        async def execute(self, statement: object) -> object:
            self.statements.append(statement)
            return AggregateResult() if len(self.statements) == 1 else PageResult()

    session = FakeSession()
    result = asyncio.run(
        search_staff(
            session,  # type: ignore[arg-type]
            StaffSearchQuery(page=3, page_size=10),
        )
    )
    page_sql = _sql(session.statements[1])

    assert result.total == 21
    assert result.department_count == 4
    assert result.tagged_count == 18
    assert "order by lower(users.full_name), users.id" in page_sql
    assert "limit 10 offset 20" in page_sql


def test_route_returns_pagination_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(session: object, query: StaffSearchQuery) -> StaffSearchResult:
        return StaffSearchResult(
            users=[],
            total=21,
            department_count=4,
            tagged_count=18,
        )

    monkeypatch.setattr(routes_profile, "search_staff_service", fake_search)
    actor = SimpleNamespace(
        role=UserRole.FACULTY_ADMINISTRATOR,
        is_dual_role=False,
    )
    page = asyncio.run(
        routes_profile.search_staff(
            query=StaffSearchQuery(page=3, page_size=10),
            session=object(),  # type: ignore[arg-type]
            actor=actor,  # type: ignore[arg-type]
        )
    )

    assert page.model_dump() == {
        "items": [],
        "total": 21,
        "department_count": 4,
        "tagged_count": 18,
        "page": 3,
        "page_size": 10,
        "total_pages": 3,
    }


@pytest.mark.parametrize("is_dual_role", [False, True])
def test_non_administrator_cannot_search_staff(is_dual_role: bool) -> None:
    actor = SimpleNamespace(
        id=uuid4(),
        role=UserRole.ACADEMIC_STAFF,
        is_dual_role=is_dual_role,
    )

    with pytest.raises(ForbiddenError, match="Only administrators"):
        asyncio.run(
            routes_profile.search_staff(
                query=StaffSearchQuery(),
                session=object(),  # type: ignore[arg-type]
                actor=actor,  # type: ignore[arg-type]
            )
        )


@pytest.mark.parametrize(
    "values",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_invalid_page_boundaries_are_rejected(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        StaffSearchQuery(**values)
