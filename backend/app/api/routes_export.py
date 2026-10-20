"""UC-18 — Customized one-page portfolio snapshot export."""
from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import AccountStatus, User, UserRole
from app.db.session import get_session
from app.schemas import ExportSnapshotRequest
from app.services.export import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.post(
    "/snapshot",
    summary="UC-18 — Generate and download the one-page expertise snapshot.",
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            },
            "description": "Snapshot generated.",
        }
    },
)
async def export_snapshot(
    payload: ExportSnapshotRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    buffer, mime, filename = await ExportService(session).generate(
        user_id=actor.id, request=payload
    )
    return Response(
        content=buffer,
        media_type=mime,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{quote(filename)}"'
            )
        },
    )


@router.post(
    "/staff/{user_id}/snapshot",
    summary="UC-18 — Administrator generates a staff member's one-page CV.",
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            },
            "description": "Staff snapshot generated.",
        }
    },
)
async def export_staff_snapshot(
    user_id: UUID,
    payload: ExportSnapshotRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> Response:
    if actor.role != UserRole.FACULTY_ADMINISTRATOR:
        raise ForbiddenError("Only administrators may export another staff member's CV.")

    eligible = await session.scalar(
        select(User.id).where(
            User.id == user_id,
            User.status == AccountStatus.ACTIVE,
            or_(
                User.role == UserRole.ACADEMIC_STAFF,
                User.is_dual_role.is_(True),
            ),
        )
    )
    if eligible is None:
        raise NotFoundError("Academic staff profile not found.")

    buffer, mime, filename = await ExportService(session).generate(
        user_id=user_id, request=payload
    )
    return Response(
        content=buffer,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'},
    )
