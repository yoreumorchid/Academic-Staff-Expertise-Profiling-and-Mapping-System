"""UC-15 / UC-16 / UC-17 — gap analytics and benchmarking endpoints."""
from __future__ import annotations

from typing import List
import asyncio

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import require_portfolio
from app.core.config import get_settings
from app.core.exceptions import ValidationFailure
from app.db.models import BenchmarkRun, PortfolioType, User
from app.db.session import get_session
from app.schemas import (
    BenchmarkRunOut,
    BenchmarkWhiteSpaceOut,
    GapAnalysisItem,
    GapAnalysisReport,
    DocumentPreviewOut,
)
from app.services.benchmarking import BenchmarkingService
from app.services.document_extract import extract_text_from_upload
from app.services.upload_validation import read_upload_limited
from app.services.document_representation import build_chunks, preview_documents, select_sections
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
                f"The combined peer upload exceeds the {limit_mib:g} MiB request limit."
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
    )
    return DocumentPreviewOut(**preview.as_dict())


@router.post(
    "/peer",
    response_model=BenchmarkRunOut,
    summary="UC-16 — Run a peer benchmark against uploaded curriculum documents.",
)
async def run_peer_benchmark(
    files: List[UploadFile] = File(...),
    included_section_ids: List[str] | None = Form(None),
    confirm_programme_coverage: bool = Form(False),
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
    )
    if preview.appears_single_course and not confirm_programme_coverage:
        raise ValidationFailure(
            "The upload appears to cover only one course. Confirm adequate programme "
            "coverage or add wider curriculum documents before benchmarking."
        )
    sections = select_sections(preview, included_section_ids)
    chunks, _ = await asyncio.to_thread(
        build_chunks,
        sections,
        max_source_tokens=settings.peer_document_max_source_tokens,
        max_chunks=settings.peer_document_max_chunks,
    )
    run = await BenchmarkingService(session).run_peer_benchmark(
        triggered_by=actor.id, peer_chunks=chunks
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
        missing_sources=payload["missing_sources"],
        warnings=payload["warnings"],
        weighting=payload["weighting"],
    )


def _to_run_out(run: BenchmarkRun) -> BenchmarkRunOut:
    return BenchmarkRunOut(
        id=run.id,
        benchmark_type=run.benchmark_type,
        narrative=run.narrative,
        source_payload=run.source_payload,
        visualization_payload=run.visualization_payload,
        white_spaces=[
            BenchmarkWhiteSpaceOut.model_validate(ws) for ws in run.white_spaces
        ],
    )
