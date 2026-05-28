"""UC-15 / UC-16 / UC-17 — gap analytics and benchmarking endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import require_portfolio
from app.core.exceptions import ValidationFailure
from app.db.models import BenchmarkRun, PortfolioType, User
from app.db.session import get_session
from app.schemas import (
    BenchmarkRunOut,
    BenchmarkWhiteSpaceOut,
    GapAnalysisItem,
    GapAnalysisReport,
)
from app.services.benchmarking import BenchmarkingService
from app.services.document_extract import extract_text_from_upload
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/benchmarking", tags=["benchmarking"])

_AUTHORIZED_PORTFOLIOS = (
    PortfolioType.FACULTY_MANAGER,
    PortfolioType.HEAD_OF_DEPARTMENT,
    PortfolioType.DEPUTY_DEAN_UGPG,
)


@router.post(
    "/global",
    response_model=BenchmarkRunOut,
    summary="UC-15 — Run a global benchmark against IEEE Xplore frontier metrics.",
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
    "/peer",
    response_model=BenchmarkRunOut,
    summary="UC-16 — Run a peer benchmark against uploaded curriculum documents.",
)
async def run_peer_benchmark(
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_portfolio(*_AUTHORIZED_PORTFOLIOS)),
) -> BenchmarkRunOut:
    if not files:
        raise ValidationFailure("Upload at least one peer curriculum document.")
    parsed: list[tuple[str, str]] = []
    for upload in files:
        buffer = await upload.read()
        text = await extract_text_from_upload(
            upload.filename or "peer.pdf", buffer
        )
        parsed.append((upload.filename or "peer.pdf", text))
    run = await BenchmarkingService(session).run_peer_benchmark(
        triggered_by=actor.id, peer_documents=parsed
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
    )


def _to_run_out(run: BenchmarkRun) -> BenchmarkRunOut:
    return BenchmarkRunOut(
        id=run.id,
        benchmark_type=run.benchmark_type,
        narrative=run.narrative,
        visualization_payload=run.visualization_payload,
        white_spaces=[
            BenchmarkWhiteSpaceOut.model_validate(ws) for ws in run.white_spaces
        ],
    )
