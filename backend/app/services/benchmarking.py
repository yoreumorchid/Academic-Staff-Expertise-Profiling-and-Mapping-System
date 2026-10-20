"""Deterministic gap analytics and benchmarking workflows (UC-15/16/17)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, RateLimitError, ValidationFailure
from app.db.models import (
    BenchmarkRun,
    BenchmarkType,
    BenchmarkWhiteSpace,
)
from app.services.document_representation import SourceSection, sections_payload
from app.services.embeddings import embed_texts
from app.services.external_apis import OpenAlexClient
from app.services.internal_expertise import StaffExpertiseProfile, load_internal_expertise
from app.services.llm_normalize import synthesize_narrative

logger = logging.getLogger(__name__)

GLOBAL_TOPICS_PER_SUBFIELD = 2
BENCHMARK_HISTORY_LIMIT = 5
_BENCHMARK_RUN_LOCK_KEY = "expertise-insight-benchmark-run"

# Peer uploads are descriptive overviews until a faculty-validated comparison
# method exists. Only Global evidence currently contributes to Gap Analytics.
COMBINED_SOURCE_WEIGHTS = {
    BenchmarkType.GLOBAL: 1.0,
    BenchmarkType.PEER: 0.0,
}


@dataclass(frozen=True)
class BenchmarkEvidence:
    domain_label: str
    displacement_score: Optional[float]
    recommendation: Optional[str] = None
    peer_filename: Optional[str] = None
    detected_section: Optional[str] = None
    source_excerpt: Optional[str] = None
    nearest_staff_id: Optional[UUID] = None
    nearest_staff_name: Optional[str] = None
    nearest_cluster_label: Optional[str] = None
    nearest_cluster_distance: Optional[float] = None
    coverage_classification: Optional[str] = None
    review_status: Optional[str] = None
    external_source_id: Optional[str] = None
    external_subfield: Optional[str] = None
    external_works_count: Optional[int] = None
    external_updated_date: Optional[str] = None


class BenchmarkingService:
    """High-level orchestration for the gap analytics module."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._openalex = OpenAlexClient()

    async def run_global_benchmark(self, *, triggered_by: UUID) -> BenchmarkRun:
        await self._acquire_run_lock()
        await self._enforce_global_daily_limit()
        internal_centroids, internal_labels = await self._cluster_internal_expertise()
        if not internal_centroids:
            raise ValidationFailure(
                "Insufficient internal expertise data to compare against global topics. "
                "Trigger an expertise sync first."
            )
        retrieved_at = datetime.now(timezone.utc).isoformat()
        topic_payload, global_vectors, global_labels = await self._fetch_global_vectors()
        topics = topic_payload["topics"]
        coverage_evidence = self._compute_global_coverage(
            internal_centroids, internal_labels, global_vectors, topics
        )
        visualization = self._build_visualization_payload(
            internal_centroids, internal_labels, global_vectors, global_labels,
            external_kind="global",
        )
        return await self._persist_run(
            triggered_by=triggered_by,
            benchmark_type=BenchmarkType.GLOBAL,
            source_payload={
                "provider": "OpenAlex",
                "retrieved_at": retrieved_at,
                "scope": topic_payload["field"],
                "source_endpoint": "/works",
                "selection": {
                    "strategy": "top_research_output_topics_per_computer_science_subfield",
                    "topics_per_subfield": GLOBAL_TOPICS_PER_SUBFIELD,
                    "group_by": "primary_topic.id",
                    "work_types": ["article", "review", "book", "book-chapter"],
                    "time_series_used": False,
                },
                "embedding_model": get_settings().embedding_model,
                "embedding_input": "topic display_name + description",
                "distance_formula": "1 - max cosine_similarity(topic, internal_cluster_centroid)",
                "internal_clusters": [
                    {"label": label, "centroid": centroid}
                    for label, centroid in zip(internal_labels, internal_centroids)
                ],
                "topics": [
                    {**topic, "embedding": vector}
                    for topic, vector in zip(topics, global_vectors)
                ],
                "interpretation": (
                    "Current cross-subfield topic coverage for administrator review; "
                    "not an emerging-trend or automatic staffing-gap score."
                ),
            },
            visualization=visualization,
            narrative=None,
            white_spaces=coverage_evidence,
        )

    async def run_peer_overview(
        self, *, triggered_by: UUID, peer_sections: Sequence[SourceSection]
    ) -> BenchmarkRun:
        if not peer_sections:
            raise ValidationFailure(
                "Include at least one curriculum section in the peer overview."
            )
        await self._acquire_run_lock()
        overview_items = [
            BenchmarkEvidence(
                domain_label=f"{section.filename} — {section.section}"[:255],
                displacement_score=None,
                peer_filename=section.filename,
                detected_section=section.section,
                source_excerpt=section.excerpt,
                review_status="source_overview",
            )
            for section in peer_sections
        ]
        return await self._persist_run(
            triggered_by=triggered_by,
            benchmark_type=BenchmarkType.PEER,
            source_payload={
                "documents": sorted({section.filename for section in peer_sections}),
                "section_count": len(peer_sections),
                "sections": sections_payload(peer_sections),
                "mode": "descriptive_curriculum_overview",
                "staff_comparison_used": False,
                "gap_classification_used": False,
                "interpretation": (
                    "Descriptive overview of selected academic curriculum content. "
                    "It is not evidence of an institutional expertise gap."
                ),
            },
            visualization=None,
            narrative=None,
            white_spaces=overview_items,
        )

    async def generate_combined_report(self, *, triggered_by: UUID) -> Dict:
        latest_global = await self._latest_run(BenchmarkType.GLOBAL)
        if latest_global is None:
            raise ValidationFailure(
                "No Global benchmark report is available. Run Global Topic Coverage first."
            )
        combined_spaces = self._combine_evidence(latest_global, None)
        missing_sources: List[str] = []
        warnings = [
            "Peer curriculum reports are descriptive overviews and are intentionally "
            "excluded from Gap Analytics until a faculty-validated comparison method exists."
        ]
        narrative = await synthesize_narrative(
            self._combined_prompt(combined_spaces)
        )
        return {
            "narrative": narrative,
            "white_spaces": combined_spaces,
            "global_run_id": str(latest_global.id) if latest_global else None,
            "peer_run_id": None,
            "global_run_created_at": latest_global.created_at if latest_global else None,
            "peer_run_created_at": None,
            "missing_sources": missing_sources,
            "warnings": warnings,
            "weighting": {
                "status": "global_only_peer_analysis_deferred",
                "global_weight": COMBINED_SOURCE_WEIGHTS[BenchmarkType.GLOBAL],
                "peer_weight": COMBINED_SOURCE_WEIGHTS[BenchmarkType.PEER],
                "normalization": "within_source_dense_rank_percentile",
                "formula": (
                    "weighted_priority_score = global_relative_priority"
                ),
                "interpretation": (
                    "Global topic-coverage review order only. Peer curriculum overview "
                    "is not included in scoring."
                ),
            },
        }

    @classmethod
    def _combine_evidence(
        cls,
        latest_global: Optional[BenchmarkRun],
        latest_peer: Optional[BenchmarkRun],
    ) -> List[Dict]:
        """Build a Global-only review queue without inventing Peer alignment.

        Only Global evidence is currently eligible. Peer uploads are descriptive
        curriculum overviews and must not enter gap scoring.
        """
        combined: List[Dict] = []
        for run in (latest_global, latest_peer):
            if run is None or run.benchmark_type != BenchmarkType.GLOBAL:
                continue
            comparable_spaces = [
                space for space in run.white_spaces
                if space.displacement_score is not None
            ]
            relative_scores = cls._relative_priority_scores(comparable_spaces)
            source_weight = COMBINED_SOURCE_WEIGHTS[run.benchmark_type]
            for space, relative_score in zip(comparable_spaces, relative_scores):
                combined.append({
                    "source": run.benchmark_type.value,
                    "domain_label": space.domain_label,
                    "displacement_score": space.displacement_score,
                    "source_relative_priority": relative_score,
                    "source_weight": source_weight,
                    "weighted_priority_score": source_weight * relative_score,
                    "recommendation": space.recommendation,
                    "peer_filename": space.peer_filename,
                    "detected_section": space.detected_section,
                    "source_excerpt": space.source_excerpt,
                    "nearest_staff_id": space.nearest_staff_id,
                    "nearest_staff_name": space.nearest_staff_name,
                    "nearest_cluster_label": space.nearest_cluster_label,
                    "nearest_cluster_distance": space.nearest_cluster_distance,
                    "coverage_classification": space.coverage_classification,
                    "review_status": space.review_status,
                    "external_source_id": space.external_source_id,
                    "external_subfield": space.external_subfield,
                    "external_works_count": space.external_works_count,
                    "external_updated_date": space.external_updated_date,
                })
        return sorted(
            combined,
            key=lambda item: (
                -item["weighted_priority_score"],
                -item["displacement_score"],
                item["source"],
                item["domain_label"].casefold(),
            ),
        )

    @staticmethod
    def _relative_priority_scores(
        spaces: Sequence[BenchmarkWhiteSpace],
    ) -> List[float]:
        """Return dense-rank percentiles where 1 is weakest internal coverage."""
        if not spaces:
            return []
        distinct = sorted(
            {float(space.displacement_score) for space in spaces}, reverse=True
        )
        if len(distinct) == 1:
            return [1.0 for _ in spaces]
        score_by_distance = {
            distance: 1.0 - (rank / (len(distinct) - 1))
            for rank, distance in enumerate(distinct)
        }
        return [score_by_distance[float(space.displacement_score)] for space in spaces]

    async def _cluster_internal_expertise(
        self,
    ) -> Tuple[List[List[float]], List[str]]:
        _, centroids, labels = await self._load_internal_expertise()
        return centroids, labels

    async def _load_internal_expertise(
        self,
    ) -> Tuple[List[StaffExpertiseProfile], List[List[float]], List[str]]:
        dataset = await load_internal_expertise(self._session)
        return (
            list(dataset.profiles),
            [list(row) for row in dataset.clusters.centroids],
            list(dataset.clusters.labels),
        )

    async def _fetch_global_vectors(
        self,
    ) -> Tuple[Dict[str, object], List[List[float]], List[str]]:
        payload = await self._openalex.fetch_computer_science_benchmark_topics(
            topics_per_subfield=GLOBAL_TOPICS_PER_SUBFIELD
        )
        topics = list(payload["topics"])
        embedding_inputs = [
            ". ".join(
                part.strip()
                for part in (topic.get("display_name"), topic.get("description"))
                if isinstance(part, str) and part.strip()
            )
            for topic in topics
        ]
        vectors = await embed_texts(embedding_inputs)
        aligned_topics = topics[:len(vectors)]
        payload["topics"] = aligned_topics
        return payload, vectors, [str(topic["display_name"]) for topic in aligned_topics]

    @staticmethod
    def _compute_global_coverage(
        internal_centroids: Sequence[Sequence[float]],
        internal_labels: Sequence[str],
        external_vectors: Sequence[Sequence[float]],
        topics: Sequence[Dict[str, object]],
    ) -> List[BenchmarkEvidence]:
        if not internal_centroids or not external_vectors:
            return []
        internal = np.asarray(internal_centroids, dtype=float)
        results: List[BenchmarkEvidence] = []
        for topic, vector in zip(topics, external_vectors):
            similarities = BenchmarkingService._cosine_similarities(
                internal, np.asarray(vector, dtype=float)
            )
            index = int(np.argmax(similarities))
            distance = float(1.0 - similarities[index])
            recommendation = (
                f"Closest internal capability cluster: '{internal_labels[index]}'. "
                "Review alongside programme priorities and staff workload before action."
                if internal_labels else None
            )
            results.append(BenchmarkEvidence(
                domain_label=str(topic.get("display_name") or topic.get("id")),
                displacement_score=distance,
                recommendation=recommendation,
                source_excerpt=(
                    str(topic["description"]) if topic.get("description") else None
                ),
                nearest_cluster_label=(internal_labels[index] if internal_labels else None),
                nearest_cluster_distance=distance,
                review_status="pending_administrator_review",
                external_source_id=str(topic.get("id") or "") or None,
                external_subfield=str(topic.get("subfield_name") or "") or None,
                external_works_count=int(topic.get("research_output_count") or 0),
                external_updated_date=(
                    str(topic["updated_date"]) if topic.get("updated_date") else None
                ),
            ))
        results.sort(key=lambda item: item.displacement_score, reverse=True)
        return results

    @staticmethod
    @staticmethod
    def _cosine_similarities(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
        numerator = matrix @ vector
        denominator = np.linalg.norm(matrix, axis=1) * np.linalg.norm(vector)
        denominator[denominator == 0.0] = 1e-12
        return numerator / denominator

    @staticmethod
    def _build_visualization_payload(
        internal_centroids: Sequence[Sequence[float]],
        internal_labels: Sequence[str],
        external_vectors: Sequence[Sequence[float]],
        external_labels: Sequence[str],
        *, external_kind: str,
    ) -> Dict:
        combined = list(internal_centroids) + list(external_vectors)
        if len(combined) < 3:
            return {"points": []}
        matrix = np.asarray(combined, dtype=float)
        try:
            import umap  # type: ignore
            coordinates = umap.UMAP(
                n_components=2,
                n_neighbors=min(5, len(matrix) - 1),
                random_state=42,
                metric="cosine",
            ).fit_transform(matrix)
        except Exception:  # noqa: BLE001
            logger.exception("UMAP projection failed; falling back to PCA")
            from sklearn.decomposition import PCA
            coordinates = PCA(n_components=2, random_state=42).fit_transform(matrix)
        cutoff = len(internal_centroids)
        return {"points": [
            {
                "x": float(x),
                "y": float(y),
                "label": internal_labels[index] if index < cutoff else external_labels[index - cutoff],
                "kind": "internal" if index < cutoff else external_kind,
            }
            for index, (x, y) in enumerate(coordinates)
        ]}

    async def _persist_run(
        self, *, triggered_by: UUID, benchmark_type: BenchmarkType,
        source_payload: Dict, visualization: Optional[Dict], narrative: Optional[str],
        white_spaces: Sequence[BenchmarkEvidence],
    ) -> BenchmarkRun:
        run = BenchmarkRun(
            triggered_by=triggered_by,
            benchmark_type=benchmark_type,
            source_payload=source_payload,
            visualization_payload=visualization,
            narrative=narrative,
        )
        self._session.add(run)
        await self._session.flush()
        for item in white_spaces:
            self._session.add(BenchmarkWhiteSpace(
                run_id=run.id,
                domain_label=item.domain_label,
                displacement_score=item.displacement_score,
                recommendation=item.recommendation,
                peer_filename=item.peer_filename,
                detected_section=item.detected_section,
                source_excerpt=item.source_excerpt,
                nearest_staff_id=item.nearest_staff_id,
                nearest_staff_name=item.nearest_staff_name,
                nearest_cluster_label=item.nearest_cluster_label,
                nearest_cluster_distance=item.nearest_cluster_distance,
                coverage_classification=item.coverage_classification,
                review_status=item.review_status,
                external_source_id=item.external_source_id,
                external_subfield=item.external_subfield,
                external_works_count=item.external_works_count,
                external_updated_date=item.external_updated_date,
            ))
        await self._session.flush()
        stale_ids = list((await self._session.execute(
            select(BenchmarkRun.id)
            .where(BenchmarkRun.benchmark_type == benchmark_type)
            .order_by(BenchmarkRun.created_at.desc(), BenchmarkRun.id.desc())
            .offset(BENCHMARK_HISTORY_LIMIT)
        )).scalars())
        if stale_ids:
            await self._session.execute(
                delete(BenchmarkRun).where(BenchmarkRun.id.in_(stale_ids))
            )
        await self._session.commit()
        return await self._load_run(run.id)

    async def get_run(self, run_id: UUID) -> BenchmarkRun:
        stmt = select(BenchmarkRun).where(BenchmarkRun.id == run_id).options(
            selectinload(BenchmarkRun.white_spaces)
        )
        run = (await self._session.execute(stmt)).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Benchmark report was not found.")
        return run

    async def list_runs(
        self, kind: BenchmarkType, *, limit: int = BENCHMARK_HISTORY_LIMIT
    ) -> List[BenchmarkRun]:
        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.benchmark_type == kind)
            .options(selectinload(BenchmarkRun.white_spaces))
            .order_by(BenchmarkRun.created_at.desc(), BenchmarkRun.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().unique())

    async def global_runs_today(self) -> int:
        start, end = self._global_daily_window()
        stmt = select(func.count(BenchmarkRun.id)).where(
            BenchmarkRun.benchmark_type == BenchmarkType.GLOBAL,
            BenchmarkRun.created_at >= start,
            BenchmarkRun.created_at < end,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _acquire_run_lock(self) -> None:
        acquired = bool((await self._session.execute(
            select(func.pg_try_advisory_xact_lock(func.hashtext(_BENCHMARK_RUN_LOCK_KEY)))
        )).scalar_one())
        if not acquired:
            raise ConflictError(
                "Another global or peer benchmark is already running. Try again after it finishes."
            )

    async def _enforce_global_daily_limit(self) -> None:
        settings = get_settings()
        used = await self.global_runs_today()
        if used >= settings.global_benchmark_daily_limit:
            raise RateLimitError(
                "The global benchmark daily limit has been reached. Try again tomorrow.",
                details={
                    "daily_limit": settings.global_benchmark_daily_limit,
                    "runs_today": used,
                    "timezone": settings.global_benchmark_daily_timezone,
                },
            )

    @staticmethod
    def _global_daily_window(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        settings = get_settings()
        local_zone = ZoneInfo(settings.global_benchmark_daily_timezone)
        current = now.astimezone(local_zone) if now else datetime.now(local_zone)
        start_local = datetime.combine(current.date(), time.min, tzinfo=local_zone)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    async def _load_run(self, run_id: UUID) -> BenchmarkRun:
        return await self.get_run(run_id)

    async def _latest_run(self, kind: BenchmarkType) -> Optional[BenchmarkRun]:
        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.benchmark_type == kind)
            .options(selectinload(BenchmarkRun.white_spaces))
            .order_by(BenchmarkRun.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _combined_prompt(items: Sequence[Dict]) -> str:
        rendered = "\n".join(
            f"- [{item['source']}] {item['domain_label']} "
            f"(raw_distance={item['displacement_score']:.2f}, "
            f"relative_priority={item['source_relative_priority']:.2f}, "
            f"weighted_priority={item['weighted_priority_score']:.2f})"
            for item in items[:15]
        )
        return (
            "Summarize Global topic-coverage evidence. Peer curriculum uploads are "
            "descriptive overviews and are intentionally excluded from this analysis. "
            "Do not call any "
            "item a proven institutional gap; administrator review is required. "
            "The relative priority is a Global-only review-order score; it is not a "
            "probability or gap-severity measurement. "
            "Limit the response to roughly 300 words.\n\n"
            f"Aggregated evidence:\n{rendered}"
        )
