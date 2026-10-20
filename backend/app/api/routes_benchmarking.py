"""UC-15 / UC-16 / UC-17 — gap analytics and benchmarking endpoints."""
from __future__ import annotations

from typing import List
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import require_portfolio
from app.core.config import get_settings
from app.core.exceptions import ValidationFailure
from app.db.models import BenchmarkRun, BenchmarkType, PortfolioType, User
from app.db.session import get_session
from app.schemas import (
    BenchmarkRunOut,
    BenchmarkHistoryOut,
    BenchmarkRunSummaryOut,
    BenchmarkWhiteSpaceOut,
    GapAnalysisItem,
    GapAnalysisReport,
    DocumentPreviewOut,
)
from app.services.benchmarking import BenchmarkingService
from app.services.document_extract import extract_text_from_upload
from app.services.upload_validation import read_upload_limited
from app.services.document_representation import preview_documents, select_sections
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/benchmarking", tags=["benchmarking"])

_AUTHORIZED_PORTFOLIOS = (
    PortfolioType.FACULTY_MANAGER,
    PortfolioType.HEAD_OF_DEPARTMENT,
    PortfolioType.DEPUTY_DEAN_UGPG,
)


async def _extract_peer_uploads(
    files: List[UploadFile],
) -> list[tuple[str, str]]:
    settings = get_settings()
    if len(files) > settings.peer_document_max_files:
        raise ValidationFailure(
            f"Upload at most {settings.peer_document_max_files} peer curriculum files per analysis."
        )
    parsed: list[tuple[str, str]] = []
    total_bytes = 0
    for upload in files:
        buffer = await read_upload_limited(upload, settings.max_document_upload_bytes)
        total_bytes += len(buffer)
        if total_bytes > settings.peer_document_max_total_bytes:
            limit_mib = settings.peer_document_max_total_bytes / (1024 * 1024)
            raise ValidationFailure(
                f"The total Peer upload exceeds the {limit_mib:g} MiB request limit."
            )
        filename = upload.filename or "peer.pdf"
        parsed.append(
            (
                filename,
                await extract_text_from_upload(filename, buffer, upload.content_type),
            )
        )
    return parsed


@router.post(
    "/global",
    response_model=BenchmarkRunOut,
    summary="UC-15 — Review internal coverage of prominent OpenAlex CS topics.",
)
async def run_global_benchmark(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> BenchmarkRunOut:
    run = await BenchmarkingService(session).run_global_benchmark(
        triggered_by=actor.id
    )
    return _to_run_out(run)


@router.get(
    "/history",
    response_model=BenchmarkHistoryOut,
    summary="List retained Global reports and Peer curriculum overviews.",
)
async def benchmark_history(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> BenchmarkHistoryOut:
    service = BenchmarkingService(session)
    global_runs = await service.list_runs(BenchmarkType.GLOBAL)
    peer_runs = await service.list_runs(BenchmarkType.PEER)
    settings = get_settings()
    return BenchmarkHistoryOut(
        global_runs=[_to_run_summary(run) for run in global_runs],
        peer_runs=[_to_run_summary(run) for run in peer_runs],
        global_daily_limit=settings.global_benchmark_daily_limit,
        global_runs_today=await service.global_runs_today(),
        daily_timezone=settings.global_benchmark_daily_timezone,
    )


@router.get(
    "/runs/{run_id}",
    response_model=BenchmarkRunOut,
    summary="Open a retained benchmark report.",
)
async def get_benchmark_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> BenchmarkRunOut:
    return _to_run_out(await BenchmarkingService(session).get_run(run_id))


@router.post(
    "/peer/preview",
    response_model=DocumentPreviewOut,
    summary="DOCREP-01 — Preview cleaned peer-curriculum sections.",
)
async def preview_peer_documents(
    files: List[UploadFile] = File(...),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> DocumentPreviewOut:
    parsed = await _extract_peer_uploads(files)
    settings = get_settings()
    preview = await asyncio.to_thread(
        preview_documents,
        parsed,
        max_source_tokens=settings.peer_document_max_source_tokens,
        max_chunks=settings.peer_document_max_chunks,
        exclude_peer_administrative=True,
    )
    return DocumentPreviewOut(**preview.as_dict())


@router.post(
    "/peer",
    response_model=BenchmarkRunOut,
    summary="UC-16 — Create a descriptive peer-curriculum overview.",
)
async def run_peer_benchmark(
    files: List[UploadFile] = File(...),
    included_section_ids: List[str] | None = Form(None),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> BenchmarkRunOut:
    if not files:
        raise ValidationFailure("Upload at least one peer curriculum document.")
    parsed = await _extract_peer_uploads(files)
    settings = get_settings()
    preview = await asyncio.to_thread(
        preview_documents,
        parsed,
        max_source_tokens=settings.peer_document_max_source_tokens,
        max_chunks=settings.peer_document_max_chunks,
        exclude_peer_administrative=True,
    )
    sections = select_sections(preview, included_section_ids)
    run = await BenchmarkingService(session).run_peer_overview(
        triggered_by=actor.id, peer_sections=sections
    )
    return _to_run_out(run)


@router.post(
    "/combined",
    response_model=GapAnalysisReport,
    summary="UC-17 — Produce the combined gap analysis report.",
)
async def combined_report(
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> GapAnalysisReport:
    payload = await BenchmarkingService(session).generate_combined_report(
        triggered_by=actor.id
    )
    return GapAnalysisReport(
        narrative=payload["narrative"],
        white_spaces=[GapAnalysisItem(**item) for item in payload["white_spaces"]],
        global_run_id=payload["global_run_id"],
        peer_run_id=payload["peer_run_id"],
        global_run_created_at=payload["global_run_created_at"],
        peer_run_created_at=payload["peer_run_created_at"],
        missing_sources=payload["missing_sources"],
        warnings=payload["warnings"],
        weighting=payload["weighting"],
    )


def _to_run_out(run: BenchmarkRun) -> BenchmarkRunOut:
    return BenchmarkRunOut(
        id=run.id,
        benchmark_type=run.benchmark_type,
        created_at=run.created_at,
        narrative=run.narrative,
        source_payload=run.source_payload,
        visualization_payload=run.visualization_payload,
        white_spaces=[
            BenchmarkWhiteSpaceOut.model_validate(ws) for ws in run.white_spaces
        ],
    )


def _to_run_summary(run: BenchmarkRun) -> BenchmarkRunSummaryOut:
    return BenchmarkRunSummaryOut(
        id=run.id,
        benchmark_type=run.benchmark_type,
        created_at=run.created_at,
        item_count=len(run.white_spaces),
    )
