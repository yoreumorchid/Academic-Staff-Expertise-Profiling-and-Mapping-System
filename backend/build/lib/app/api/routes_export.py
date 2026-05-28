"""UC-18 — Customized one-page portfolio snapshot export."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import User
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
