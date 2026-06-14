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

    pdf_bytes = await _generate_report_pdf(report)
    safe_name = report.spec.title[:30].replace('"', '').replace("'", "")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="match_report_{safe_name}.pdf"'
        },
    )

async def _generate_report_pdf(report: MappingReport) -> bytes:
    import asyncio
    return await asyncio.to_thread(_build_pdf, report)

def _build_pdf(report: MappingReport) -> bytes:
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    spec = report.spec
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )
    styles = getSampleStyleSheet()

    s_title = ParagraphStyle("RT", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    s_meta = ParagraphStyle("RM", parent=styles["Normal"], fontSize=9, textColor=colors.grey, spaceAfter=12)
    s_label = ParagraphStyle("RL", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceAfter=2)
    s_body = ParagraphStyle("RB", parent=styles["Normal"], fontSize=10, spaceAfter=12)
    s_cell = ParagraphStyle("RC", parent=styles["Normal"], fontSize=9)

    story: list = []

    def _escp(text: str) -> str:
        return text.replace("&", "&").replace("<", "<").replace(">", ">")

    # Title
    story.append(Paragraph(f"Mapping Report: {_escp(spec.title)}", s_title))
    gen_time = report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else "N/A"
    story.append(Paragraph(f"Spec type: {_escp(spec.spec_type.value)} | Generated: {gen_time}", s_meta))

    # Spec Content
    story.append(Paragraph("SPECIFICATION CONTENT", s_label))
    story.append(Paragraph(_escp(spec.raw_text), s_body))

    # Match Results table
    story.append(Paragraph("MATCH RESULTS", s_label))
    headers = ["Rank", "Staff", "Cosine", "Spread", "Combined"]
    data = [[Paragraph(h, styles["Heading4"]) for h in headers]]
    for e in report.entries:
        data.append([
            Paragraph(str(e.rank), s_cell),
            Paragraph(str(e.user_id)[:8], s_cell),
            Paragraph(f"{e.cosine_score:.3f}", s_cell),
            Paragraph(f"{e.spreading_score:.3f}", s_cell),
            Paragraph(f"{e.combined_score:.3f}", s_cell),
        ])

    t = Table(data, colWidths=[30, 80, 60, 60, 60])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    # AI Analysis
    story.append(Paragraph("AI ANALYSIS", s_label))
    summary_text = _escp(report.summary) if report.summary else "No AI analysis generated for this report."
    story.append(Paragraph(summary_text, s_body))

    try:
        doc.build(story)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("PDF build failed: %s", exc)
        raise
    buf.seek(0)
    return buf.read()


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
