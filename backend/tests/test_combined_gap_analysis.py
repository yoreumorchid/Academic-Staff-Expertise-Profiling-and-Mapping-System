"""Focused BENCH-03 aggregation formula and API-contract regressions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import BenchmarkType
from app.schemas import GapAnalysisReport
from app.services import benchmarking
from app.services.benchmarking import BenchmarkingService


def _evidence(label: str, distance: float, **overrides):
    values = {
        "domain_label": label,
        "displacement_score": distance,
        "recommendation": "Review with faculty management.",
        "peer_filename": None,
        "detected_section": None,
        "source_excerpt": f"Evidence for {label}",
        "nearest_staff_id": None,
        "nearest_staff_name": None,
        "nearest_cluster_label": "Internal cluster",
        "nearest_cluster_distance": distance,
        "coverage_classification": None,
        "review_status": "pending_administrator_review",
        "external_source_id": None,
        "external_subfield": None,
        "external_works_count": None,
        "external_updated_date": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _run(kind: BenchmarkType, evidence: list[SimpleNamespace]):
    return SimpleNamespace(
        id=uuid4(),
        benchmark_type=kind,
        created_at=datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc),
        white_spaces=evidence,
    )


def test_combined_priority_uses_global_evidence_and_excludes_peer_overview() -> None:
    global_run = _run(BenchmarkType.GLOBAL, [
        _evidence("Global weak", 0.90, external_source_id="T1"),
        _evidence("Global strong", 0.20, external_source_id="T2"),
    ])
    peer_run = _run(BenchmarkType.PEER, [
        _evidence("Peer weak", 0.75, peer_filename="peer.pdf", nearest_staff_name="Staff A"),
        _evidence("Peer strong", 0.30, peer_filename="peer.pdf", nearest_staff_name="Staff B"),
    ])

    items = BenchmarkingService._combine_evidence(global_run, peer_run)

    assert [item["weighted_priority_score"] for item in items] == [1.0, 0.0]
    assert {item["source"] for item in items} == {"global"}
    assert next(item for item in items if item["domain_label"] == "Global weak")["external_source_id"] == "T1"
    assert all(item["review_status"] == "pending_administrator_review" for item in items)


def test_relative_priority_uses_dense_ranks_and_preserves_ties() -> None:
    spaces = [_evidence("A", 0.8), _evidence("B", 0.8), _evidence("C", 0.5)]

    assert BenchmarkingService._relative_priority_scores(spaces) == [1.0, 1.0, 0.0]


def test_combined_report_explicitly_defers_peer_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    global_run = _run(BenchmarkType.GLOBAL, [_evidence("Global only", 0.6)])
    service = BenchmarkingService(SimpleNamespace())

    async def fake_latest(kind: BenchmarkType):
        return global_run if kind == BenchmarkType.GLOBAL else None

    async def fake_narrative(prompt: str) -> str:
        return "Global coverage summary."

    monkeypatch.setattr(service, "_latest_run", fake_latest)
    monkeypatch.setattr(benchmarking, "synthesize_narrative", fake_narrative)

    report = asyncio.run(service.generate_combined_report(triggered_by=uuid4()))

    assert report["missing_sources"] == []
    assert report["weighting"]["status"] == "global_only_peer_analysis_deferred"
    assert report["weighting"]["global_weight"] == 1.0
    assert report["weighting"]["peer_weight"] == 0.0
    assert report["white_spaces"][0]["weighted_priority_score"] == 1.0
    assert "intentionally excluded" in report["warnings"][0]
    response = GapAnalysisReport.model_validate(report)
    assert response.white_spaces[0].source_excerpt == "Evidence for Global only"
    assert response.global_run_created_at == global_run.created_at
    assert response.peer_run_created_at is None
    assert response.weighting.status == "global_only_peer_analysis_deferred"


def test_combined_prompt_states_interpretation_boundary() -> None:
    prompt = BenchmarkingService._combined_prompt([
        {
            "source": "global",
            "domain_label": "Topic",
            "displacement_score": 0.8,
            "source_relative_priority": 1.0,
            "weighted_priority_score": 0.5,
        }
    ])

    assert "Global-only review-order score" in prompt
    assert "Peer curriculum uploads" in prompt
    assert "not a probability or gap-severity measurement" in prompt
    assert "administrator review is required" in prompt
