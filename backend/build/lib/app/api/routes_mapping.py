"""UC-13 — Course / grant specification ingestion.
UC-14 — Semantic matching against the institutional expertise database.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_portfolio
from app.core.exceptions import NotFoundError, ValidationFailure
from app.db.models import (
    CourseGrantSpec,
    MappingReport,
    PortfolioType,
    SpecificationType,
    User,
)
from app.db.session import get_session
from app.schemas import (
    MappingReportEntryOut,
    MappingReportOut,
    SpecIngestRequest,
    SpecIngestResponse,
)
from app.services.document_extract import extract_text_from_upload
from app.services.mapping import MappingService

router = APIRouter(prefix="/mapping", tags=["mapping"])

_AUTHORIZED_PORTFOLIOS = (
    PortfolioType.HEAD_OF_DEPARTMENT,
    PortfolioType.DEPUTY_DEAN_RESEARCH,
    PortfolioType.DEPUTY_DEAN_UGPG,
)


@router.post(
    "/specs",
    response_model=SpecIngestResponse,
    summary="UC-13 — Ingest a course or grant specification (text payload).",
)
async def ingest_spec_text(
    payload: SpecIngestRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> SpecIngestResponse:
    spec = await MappingService(session).ingest_specification(
        created_by=actor.id,
        spec_type=payload.spec_type,
        title=payload.title,
        raw_text=payload.raw_text,
    )
    return SpecIngestResponse.model_validate(spec)


@router.post(
    "/specs/upload",
    response_model=SpecIngestResponse,
    summary="UC-13 alt — Ingest a specification via PDF or Word upload.",
)
async def ingest_spec_upload(
    spec_type: SpecificationType = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> SpecIngestResponse:
    if not title.strip():
        raise ValidationFailure("Specification title is required.")
    buffer = await file.read()
    text = await extract_text_from_upload(file.filename or "upload", buffer)
    spec = await MappingService(session).ingest_specification(
        created_by=actor.id,
        spec_type=spec_type,
        title=title,
        raw_text=text,
        source_filename=file.filename,
    )
    return SpecIngestResponse.model_validate(spec)


@router.post(
    "/specs/{spec_id}/match",
    response_model=MappingReportOut,
    summary="UC-14 — Generate a ranked semantic matching report.",
)
async def generate_mapping_report(
    spec_id: UUID,
    top_n: int = 25,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> MappingReportOut:
    report = await MappingService(session).generate_report(
        spec_id=spec_id, generated_by=actor.id, top_n=top_n
    )
    if not report.entries:
        # UC-14 exception: insufficient expertise match.
        raise ValidationFailure(
            "No academic staff met the minimum semantic proximity threshold "
            "for the given specifications.",
        )
    return _to_report_out(report)


@router.get(
    "/specs",
    response_model=List[SpecIngestResponse],
    summary="UC-13 — List previously ingested specifications.",
)
async def list_specs(
    spec_type: Optional[SpecificationType] = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> List[SpecIngestResponse]:
    stmt = select(CourseGrantSpec).order_by(CourseGrantSpec.created_at.desc()).limit(50)
    if spec_type is not None:
        stmt = stmt.where(CourseGrantSpec.spec_type == spec_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [SpecIngestResponse.model_validate(row) for row in rows]


@router.get(
    "/reports/{report_id}",
    response_model=MappingReportOut,
    summary="UC-14 — Retrieve a previously generated report.",
)
async def get_mapping_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> MappingReportOut:
    stmt = (
        select(MappingReport)
        .where(MappingReport.id == report_id)
        .options(selectinload(MappingReport.entries))
    )
    report = (await session.execute(stmt)).scalar_one_or_none()
    if report is None:
        raise NotFoundError("Mapping report not found.")
    return _to_report_out(report)


def _to_report_out(report: MappingReport) -> MappingReportOut:
    return MappingReportOut(
        id=report.id,
        spec_id=report.spec_id,
        summary=report.summary,
        entries=[
            MappingReportEntryOut(
                user_id=entry.user_id,
                rank=entry.rank,
                cosine_score=entry.cosine_score,
                spreading_score=entry.spreading_score,
                combined_score=entry.combined_score,
                is_cross_department=entry.is_cross_department,
            )
            for entry in report.entries
        ],
    )
