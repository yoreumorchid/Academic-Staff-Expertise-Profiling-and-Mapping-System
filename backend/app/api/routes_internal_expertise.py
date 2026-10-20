"""Authenticated internal capability overview independent of benchmarking."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import InternalExpertiseOverview
from app.services.internal_expertise import (
    load_internal_expertise,
    summarize_internal_expertise,
)

router = APIRouter(prefix="/expertise", tags=["expertise"])


@router.get(
    "/internal",
    response_model=InternalExpertiseOverview,
    summary="UC-6 — View the current internal expertise capability clusters.",
)
async def get_internal_expertise(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_current_user),
) -> InternalExpertiseOverview:
    # Authentication is intentionally the only visibility boundary. The
    # response is aggregate and does not disclose individual assignments.
    del actor
    dataset = await load_internal_expertise(session, include_clusters=False)
    return InternalExpertiseOverview.model_validate(
        summarize_internal_expertise(dataset)
    )
