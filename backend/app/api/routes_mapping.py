"""UC-13 — Course / grant specification ingestion.
UC-14 — Semantic matching against the institutional expertise database.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_portfolio
from app.core.config import get_settings
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
from app.services.mapping_export import render_mapping_report_pdf
from app.services.upload_validation import read_upload_limited

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
    buffer = await read_upload_limited(file, get_settings().max_document_upload_bytes)
    text = await extract_text_from_upload(
        file.filename or "upload", buffer, file.content_type
    )
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
    stmt = (
        select(CourseGrantSpec)
        .options(selectinload(CourseGrantSpec.reports))
        .order_by(CourseGrantSpec.created_at.desc())
        .limit(50)
    )
    if spec_type is not None:
        stmt = stmt.where(CourseGrantSpec.spec_type == spec_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [_spec_to_out(row) for row in rows]

def _spec_to_out(spec: CourseGrantSpec) -> SpecIngestResponse:
    latest_report_id = spec.reports[-1].id if spec.reports else None
    return SpecIngestResponse(
        id=spec.id,
        spec_type=spec.spec_type,
        title=spec.title,
        source_filename=spec.source_filename,
        latest_report_id=latest_report_id,
    )

@router.delete(
    "/specs/{spec_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="UC-13 — Delete an ingested specification and its reports.",
)
async def delete_spec(
    spec_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> None:
    spec = await session.get(CourseGrantSpec, spec_id)
    if spec is None:
        raise NotFoundError("Specification not found.")
    await session.delete(spec)
    await session.commit()

@router.get(
    "/specs/{spec_id}/export",
    summary="UC-14 — Export the latest match report as PDF.",
)
async def export_report(
    spec_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> Response:
    stmt = (
        select(MappingReport)
        .where(MappingReport.spec_id == spec_id)
        .options(
            selectinload(MappingReport.entries),
            selectinload(MappingReport.spec),
        )
        .order_by(MappingReport.created_at.desc())
        .limit(1)
    )
    report = (await session.execute(stmt)).scalar_one_or_none()
    if report is None:
        raise NotFoundError("No report found for this specification. Run a match first.")

    pdf_bytes = await render_mapping_report_pdf(report)
    safe_name = report.spec.title[:30].replace('"', '').replace("'", "")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="match_report_{safe_name}.pdf"'
        },
    )

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
        .options(
            selectinload(MappingReport.entries),
            selectinload(MappingReport.spec),
        )
    )
    report = (await session.execute(stmt)).scalar_one_or_none()
    if report is None:
        raise NotFoundError("Mapping report not found.")
    return _to_report_out(report)


def _to_report_out(report: MappingReport) -> MappingReportOut:
    spec = report.spec
    return MappingReportOut(
        id=report.id,
        spec_id=report.spec_id,
        spec_title=spec.title,
        spec_text=spec.raw_text,
        summary=report.summary,
        entries=[
            MappingReportEntryOut(
                user_id=entry.user_id,
                rank=entry.rank,
                cosine_score=entry.cosine_score,
                spreading_score=entry.spreading_score,
                combined_score=entry.combined_score,
            )
            for entry in report.entries
        ],
    )
