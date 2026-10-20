"""Focused BENCH-02 OpenAlex contract and coverage regressions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes_benchmarking import _to_run_out
from app.core.exceptions import ConflictError, RateLimitError
from app.db.models import BenchmarkType
from app.services import external_apis
from app.services.benchmarking import BenchmarkingService
from app.services.external_apis import OpenAlexClient


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_openalex_topic_retrieval_uses_official_cs_hierarchy_and_research_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []
    responses = iter([
        _Response({
            "id": "https://openalex.org/fields/17",
            "display_name": "Computer Science",
            "updated_date": "2026-10-18T03:01:44",
            "subfields": [
                {"id": "https://openalex.org/subfields/1702", "display_name": "Artificial Intelligence"},
                {"id": "https://openalex.org/subfields/1712", "display_name": "Software"},
            ],
        }),
        _Response({"group_by": [{
            "key": "https://openalex.org/T10001",
            "key_display_name": "Machine Learning Applications",
            "count": 1234,
        }]}),
        _Response({"group_by": [{
            "key": "https://openalex.org/T10002",
            "key_display_name": "Software Engineering Research",
            "count": 987,
        }]}),
        _Response({"results": [
            {
                "id": "https://openalex.org/T10001",
                "description": "Research on machine learning applications.",
                "works_count": 1500,
                "cited_by_count": 6000,
                "updated_date": "2026-10-17T00:00:00",
            },
            {
                "id": "https://openalex.org/T10002",
                "description": "Research on software engineering.",
                "works_count": 1200,
                "cited_by_count": 4000,
                "updated_date": "2026-10-17T00:00:00",
            },
        ]}),
    ])

    async def fake_request(client, method, url, *, service_label, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return next(responses)

    monkeypatch.setattr(external_apis, "_request_with_retry", fake_request)

    payload = asyncio.run(
        OpenAlexClient().fetch_computer_science_benchmark_topics(topics_per_subfield=1)
    )

    assert payload["field"]["id"] == "17"
    assert [topic["id"] for topic in payload["topics"]] == ["T10001", "T10002"]
    assert payload["topics"][0]["research_output_count"] == 1234
    group_params = [params for url, params in calls if url.endswith("/works")]
    assert all(params["group_by"] == "primary_topic.id" for params in group_params)
    assert all("type:article|review|book|book-chapter" in params["filter"] for params in group_params)
    assert calls[-1][1]["filter"] == "id:T10001|T10002"


def test_global_coverage_keeps_provenance_and_orders_weaker_alignment_first() -> None:
    topics = [
        {
            "id": "T10001",
            "display_name": "Strongly covered topic",
            "description": "Description one",
            "subfield_name": "Artificial Intelligence",
            "research_output_count": 1000,
            "updated_date": "2026-10-17T00:00:00",
        },
        {
            "id": "T10002",
            "display_name": "Weakly covered topic",
            "description": "Description two",
            "subfield_name": "Software",
            "research_output_count": 800,
            "updated_date": "2026-10-16T00:00:00",
        },
    ]

    results = BenchmarkingService._compute_global_coverage(
        [[1.0, 0.0]],
        ["Data / AI"],
        [[1.0, 0.0], [0.0, 1.0]],
        topics,
    )

    assert [item.external_source_id for item in results] == ["T10002", "T10001"]
    assert results[0].displacement_score == pytest.approx(1.0)
    assert results[0].external_subfield == "Software"
    assert results[0].external_works_count == 800
    assert results[0].nearest_cluster_label == "Data / AI"
    assert results[0].review_status == "pending_administrator_review"


def test_global_api_contract_exposes_method_and_topic_evidence() -> None:
    evidence = SimpleNamespace(
        domain_label="Software Engineering Research",
        displacement_score=0.42,
        recommendation="Review alongside programme priorities.",
        peer_filename=None,
        detected_section=None,
        source_excerpt="Research on software engineering.",
        nearest_staff_id=None,
        nearest_staff_name=None,
        nearest_cluster_label="Systems / Software",
        nearest_cluster_distance=0.42,
        coverage_classification=None,
        review_status="pending_administrator_review",
        external_source_id="T10002",
        external_subfield="Software",
        external_works_count=987,
        external_updated_date="2026-10-17T00:00:00",
    )
    run = SimpleNamespace(
        id=uuid4(),
        benchmark_type=BenchmarkType.GLOBAL,
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        narrative=None,
        source_payload={"provider": "OpenAlex", "selection": {"time_series_used": False}},
        visualization_payload={"points": []},
        white_spaces=[evidence],
    )

    response = _to_run_out(run)

    assert response.source_payload["provider"] == "OpenAlex"
    assert response.source_payload["selection"]["time_series_used"] is False
    assert response.white_spaces[0].external_source_id == "T10002"
    assert response.white_spaces[0].external_works_count == 987


def test_global_daily_window_uses_configured_local_calendar_day() -> None:
    start, end = BenchmarkingService._global_daily_window(
        datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)
    )

    assert start == datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


def test_benchmark_lock_rejects_a_concurrent_global_or_peer_run() -> None:
    class _Result:
        def scalar_one(self) -> bool:
            return False

    class _Session:
        async def execute(self, statement: object) -> _Result:
            return _Result()

    with pytest.raises(ConflictError, match="already running"):
        asyncio.run(BenchmarkingService(_Session())._acquire_run_lock())  # type: ignore[arg-type]


def test_global_daily_limit_is_enforced_before_expensive_work() -> None:
    service = BenchmarkingService(SimpleNamespace())

    async def at_limit() -> int:
        return 5

    service.global_runs_today = at_limit  # type: ignore[method-assign]

    with pytest.raises(RateLimitError, match="daily limit"):
        asyncio.run(service._enforce_global_daily_limit())


def test_global_run_does_not_generate_an_llm_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    service = BenchmarkingService(SimpleNamespace())
    captured: dict[str, object] = {}

    async def no_op() -> None:
        return None

    async def clusters():
        return [[1.0, 0.0]], ["Data / AI"]

    async def global_vectors():
        topic = {"id": "T1", "display_name": "AI", "research_output_count": 1}
        return {"field": {"display_name": "Computer Science"}, "topics": [topic]}, [[1.0, 0.0]], ["AI"]

    async def persist(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid4())

    async def unexpected_summary(prompt: str) -> str:
        raise AssertionError("Global benchmarking should not call the LLM summary path")

    service._acquire_run_lock = no_op  # type: ignore[method-assign]
    service._enforce_global_daily_limit = no_op  # type: ignore[method-assign]
    service._cluster_internal_expertise = clusters  # type: ignore[method-assign]
    service._fetch_global_vectors = global_vectors  # type: ignore[method-assign]
    service._build_visualization_payload = lambda *args, **kwargs: {}  # type: ignore[method-assign]
    service._persist_run = persist  # type: ignore[method-assign]
    monkeypatch.setattr("app.services.benchmarking.synthesize_narrative", unexpected_summary)

    asyncio.run(service.run_global_benchmark(triggered_by=uuid4()))

    assert captured["narrative"] is None
