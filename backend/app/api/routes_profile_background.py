"""UC-10 academic-background CRUD and CSV import routes."""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.models import AcademicBackground, AcademicBackgroundCategory, User
from app.db.session import get_session
from app.schemas import (
    AcademicBackgroundCreate,
    AcademicBackgroundOut,
    AcademicBackgroundUpdate,
)
from app.services.upload_validation import decode_csv_upload, read_upload_limited

router = APIRouter(tags=["profile"])

_VALID_CATEGORIES = {category.value for category in AcademicBackgroundCategory}
_BACKGROUND_CSV_HEADER = [
    "category",
    "title",
    "organization",
    "description",
    "start_date",
    "end_date",
]
_TEMPLATE_EXAMPLE = """category,title,organization,description,start_date,end_date
education,PhD in Computer Science,University of Malaya,Dissertation on semantic mapping algorithms,2018-09-01,2022-06-30
award,Best Paper Award,IEEE,Outstanding contribution to semantic web research,2023-06-15,
"""


@router.get(
    "/background",
    response_model=List[AcademicBackgroundOut],
    summary="UC-10 — List the actor's academic background records.",
)
async def list_background(
    category: Optional[AcademicBackgroundCategory] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[AcademicBackgroundOut]:
    stmt = select(AcademicBackground).where(AcademicBackground.user_id == actor.id)
    if category is not None:
        stmt = stmt.where(AcademicBackground.category == category)
    stmt = stmt.order_by(AcademicBackground.start_date.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return [AcademicBackgroundOut.model_validate(row) for row in rows]


@router.post(
    "/background",
    response_model=AcademicBackgroundOut,
    status_code=status.HTTP_201_CREATED,
    summary="UC-10 — Create a new background record.",
)
async def create_background(
    payload: AcademicBackgroundCreate,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> AcademicBackgroundOut:
    record = AcademicBackground(user_id=actor.id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return AcademicBackgroundOut.model_validate(record)


@router.put(
    "/background/{record_id}",
    response_model=AcademicBackgroundOut,
    summary="UC-10 alt — Update an existing background record.",
)
async def update_background(
    record_id: UUID,
    payload: AcademicBackgroundUpdate,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> AcademicBackgroundOut:
    record = await session.get(AcademicBackground, record_id)
    if record is None or record.user_id != actor.id:
        raise NotFoundError("Background record not found.")
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return AcademicBackgroundOut.model_validate(record)


@router.delete(
    "/background/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-10 — Delete a background record.",
)
async def delete_background(
    record_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> None:
    record = await session.get(AcademicBackground, record_id)
    if record is None or record.user_id != actor.id:
        raise NotFoundError("Background record not found.")
    await session.delete(record)
    await session.commit()


@router.get(
    "/background/template",
    summary="UC-10 — Download a CSV template for bulk academic background import.",
)
async def download_background_template(
    actor: User = Depends(get_current_user),
) -> Response:
    return Response(
        content=_TEMPLATE_EXAMPLE,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=academic_background_template.csv"
            )
        },
    )


@router.post(
    "/background/upload",
    response_model=List[AcademicBackgroundOut],
    status_code=status.HTTP_201_CREATED,
    summary="UC-10 alt — Bulk-import academic background records from a CSV file.",
)
async def upload_background_csv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> List[AcademicBackgroundOut]:
    buffer = await read_upload_limited(file, get_settings().max_csv_upload_bytes)
    raw = decode_csv_upload(file.filename or "", file.content_type, buffer)

    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        raise ValidationFailure("Could not parse CSV header.")

    actual_cols = [header.strip().lower() for header in reader.fieldnames]
    if actual_cols != _BACKGROUND_CSV_HEADER:
        raise ValidationFailure(
            "CSV header mismatch. Expected columns: "
            + ", ".join(_BACKGROUND_CSV_HEADER)
            + ". Got: "
            + ", ".join(actual_cols)
        )

    row_errors: List[str] = []
    parsed_rows: List[dict] = []

    for index, raw_row in enumerate(reader, start=2):
        row = {
            key.strip().lower(): (value or "").strip()
            for key, value in raw_row.items()
        }
        errors: List[str] = []

        category = row.get("category", "").strip().lower()
        if not category:
            errors.append("category is required")
        elif category not in _VALID_CATEGORIES:
            errors.append(
                f"category '{category}' is invalid; must be one of: "
                + ", ".join(sorted(_VALID_CATEGORIES))
            )

        title = row.get("title", "")
        if not title:
            errors.append("title is required")
        elif len(title) > 255:
            errors.append("title exceeds 255 characters")

        organization = row.get("organization", "")
        if len(organization) > 255:
            errors.append("organization exceeds 255 characters")

        start_date_string = row.get("start_date", "")
        end_date_string = row.get("end_date", "")
        start_date = _parse_date(start_date_string, "start_date", errors)
        end_date = _parse_date(end_date_string, "end_date", errors)

        if start_date and end_date and end_date < start_date:
            errors.append(
                f"end_date ({end_date_string}) is before "
                f"start_date ({start_date_string})"
            )

        if errors:
            row_errors.append(f"Row {index}: " + "; ".join(errors))
        else:
            parsed_rows.append(
                {
                    "category": category,
                    "title": title,
                    "organization": organization or None,
                    "description": row.get("description", "") or None,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

    if row_errors:
        raise ValidationFailure(
            "CSV validation failed:\n" + "\n".join(row_errors[:20])
        )
    if not parsed_rows:
        raise ValidationFailure("CSV contains no valid data rows.")

    records = [AcademicBackground(user_id=actor.id, **row) for row in parsed_rows]
    session.add_all(records)
    await session.commit()
    for record in records:
        await session.refresh(record)

    return [AcademicBackgroundOut.model_validate(record) for record in records]


def _parse_date(value: str, field_name: str, errors: List[str]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field_name} '{value}' is not a valid YYYY-MM-DD date")
        return None
