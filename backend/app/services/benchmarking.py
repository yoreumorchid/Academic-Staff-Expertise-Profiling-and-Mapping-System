"""Deterministic gap analytics and benchmarking workflows (UC-15/16/17)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import ValidationFailure
from app.db.models import (
    AccountStatus,
    BenchmarkRun,
    BenchmarkType,
    BenchmarkWhiteSpace,
    User,
    UserExpertiseTag,
    UserRole,
)
from app.services.document_representation import DocumentChunk, chunks_payload
from app.services.embeddings import embed_texts
from app.services.external_apis import OpenAlexClient
from app.services.internal_expertise import (
    ExpertiseEvidence,
    StaffExpertiseProfile,
    build_staff_profiles,
    cluster_staff_profiles,
)
from app.services.llm_normalize import synthesize_narrative

logger = logging.getLogger(__name__)

GLOBAL_TOPICS_PER_SUBFIELD = 2

# Initial synthetic-development-set calibration. Re-estimate these boundaries
# with faculty-labelled examples before making accuracy claims on real data.
PEER_COVERED_MAX_DISTANCE = 0.40
PEER_PARTIAL_MAX_DISTANCE = 0.68


@dataclass(frozen=True)
class BenchmarkEvidence:
    domain_label: str
    displacement_score: float
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
        narrative = await synthesize_narrative(
            self._narrative_prompt(
                coverage_evidence,
                scope="current prominent OpenAlex Computer Science topics",
                require_administrator_review=True,
            )
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
            narrative=narrative,
            white_spaces=coverage_evidence,
        )

    async def run_peer_benchmark(
        self, *, triggered_by: UUID, peer_chunks: Sequence[DocumentChunk]
    ) -> BenchmarkRun:
        if not peer_chunks:
            raise ValidationFailure(
                "Upload at least one peer curriculum document to benchmark against."
            )
        profiles, centroids, cluster_labels = await self._load_internal_expertise()
        if not centroids:
            raise ValidationFailure(
                "Insufficient internal expertise data to compare against peers. "
                "Trigger an expertise sync first."
            )
        peer_texts = [chunk.excerpt for chunk in peer_chunks]
        peer_vectors = await embed_texts(peer_texts)
        aligned_chunks = list(peer_chunks[:len(peer_vectors)])
        peer_labels = [self._peer_label(chunk) for chunk in aligned_chunks]
        white_spaces = self._compute_peer_evidence(
            profiles, centroids, cluster_labels, peer_vectors, aligned_chunks
        )
        visualization = self._build_visualization_payload(
            centroids, cluster_labels, peer_vectors, peer_labels, external_kind="peer"
        )
        narrative = await synthesize_narrative(
            self._narrative_prompt(
                white_spaces,
                scope="peer institutional curricula",
                require_administrator_review=True,
            )
        )
        return await self._persist_run(
            triggered_by=triggered_by,
            benchmark_type=BenchmarkType.PEER,
            source_payload={
                "documents": sorted({chunk.filename for chunk in peer_chunks}),
                "chunk_count": len(peer_texts),
                "chunks": chunks_payload(peer_chunks),
                "embedding_model": get_settings().embedding_model,
                "distance_formula": "1 - cosine_similarity(peer_chunk, nearest_staff_profile)",
                "coverage_thresholds": {
                    "covered_max": PEER_COVERED_MAX_DISTANCE,
                    "partially_covered_max": PEER_PARTIAL_MAX_DISTANCE,
                    "calibration": "synthetic_development_set_pending_faculty_validation",
                },
                "weighting": "equal_per_retained_chunk",
            },
            visualization=visualization,
            narrative=narrative,
            white_spaces=white_spaces,
        )

    async def generate_combined_report(self, *, triggered_by: UUID) -> Dict:
        latest_global = await self._latest_run(BenchmarkType.GLOBAL)
        latest_peer = await self._latest_run(BenchmarkType.PEER)
        if latest_global is None and latest_peer is None:
            raise ValidationFailure(
                "No benchmark runs are available. Execute a global or peer benchmark first."
            )
        combined_spaces: List[Dict] = []
        for run in (latest_global, latest_peer):
            if run is None:
                continue
            for space in run.white_spaces:
                combined_spaces.append({
                    "source": run.benchmark_type.value,
                    "domain_label": space.domain_label,
                    "displacement_score": space.displacement_score,
                    "recommendation": space.recommendation,
                })
        narrative = await synthesize_narrative(self._combined_prompt(combined_spaces))
        return {
            "narrative": narrative,
            "white_spaces": combined_spaces,
            "global_run_id": str(latest_global.id) if latest_global else None,
            "peer_run_id": str(latest_peer.id) if latest_peer else None,
        }

    async def _cluster_internal_expertise(
        self,
    ) -> Tuple[List[List[float]], List[str]]:
        _, centroids, labels = await self._load_internal_expertise()
        return centroids, labels

    async def _load_internal_expertise(
        self,
    ) -> Tuple[List[StaffExpertiseProfile], List[List[float]], List[str]]:
        stmt = (
            select(UserExpertiseTag)
            .join(UserExpertiseTag.user)
            .where(User.status == AccountStatus.ACTIVE)
            .where(or_(User.role == UserRole.ACADEMIC_STAFF, User.is_dual_role.is_(True)))
            .options(selectinload(UserExpertiseTag.user), selectinload(UserExpertiseTag.tag))
            .order_by(UserExpertiseTag.user_id, UserExpertiseTag.tag_id)
        )
        links = list((await self._session.execute(stmt)).scalars().all())
        evidence = [
            ExpertiseEvidence(
                user_id=link.user_id,
                user_label=link.user.full_name,
                tag_label=link.tag.canonical_label,
                embedding=link.tag.embedding,
                confidence=link.confidence,
                validated=link.validated,
            )
            for link in links
        ]
        profiles = build_staff_profiles(evidence)
        result = cluster_staff_profiles(profiles)
        return profiles, [list(row) for row in result.centroids], list(result.labels)

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
    def _peer_label(chunk: DocumentChunk) -> str:
        preview = re.sub(r"\s+", " ", chunk.excerpt)[:100]
        return f"{chunk.filename} — {chunk.section}: {preview}"[:255]

    @staticmethod
    def _coverage_classification(distance: float) -> str:
        if distance <= PEER_COVERED_MAX_DISTANCE:
            return "covered"
        if distance <= PEER_PARTIAL_MAX_DISTANCE:
            return "partially_covered"
        return "candidate_gap"

    @classmethod
    def _compute_peer_evidence(
        cls,
        profiles: Sequence[StaffExpertiseProfile],
        centroids: Sequence[Sequence[float]],
        cluster_labels: Sequence[str],
        peer_vectors: Sequence[Sequence[float]],
        peer_chunks: Sequence[DocumentChunk],
    ) -> List[BenchmarkEvidence]:
        """Create reviewable evidence without discarding lower-ranked chunks."""
        if not profiles or not centroids or not peer_vectors:
            return []
        staff_matrix = np.asarray([profile.vector for profile in profiles], dtype=float)
        cluster_matrix = np.asarray(centroids, dtype=float)
        results: List[BenchmarkEvidence] = []
        for chunk, vector in zip(peer_chunks, peer_vectors):
            peer = np.asarray(vector, dtype=float)
            staff_scores = cls._cosine_similarities(staff_matrix, peer)
            cluster_scores = cls._cosine_similarities(cluster_matrix, peer)
            staff_index = int(np.argmax(staff_scores))
            cluster_index = int(np.argmax(cluster_scores))
            staff_distance = float(1.0 - staff_scores[staff_index])
            cluster_distance = float(1.0 - cluster_scores[cluster_index])
            profile = profiles[staff_index]
            results.append(BenchmarkEvidence(
                domain_label=cls._peer_label(chunk),
                displacement_score=staff_distance,
                recommendation="Candidate coverage evidence; administrator review required.",
                peer_filename=chunk.filename,
                detected_section=chunk.section,
                source_excerpt=chunk.excerpt,
                nearest_staff_id=profile.user_id if isinstance(profile.user_id, UUID) else None,
                nearest_staff_name=profile.user_label,
                nearest_cluster_label=cluster_labels[cluster_index],
                nearest_cluster_distance=cluster_distance,
                coverage_classification=cls._coverage_classification(staff_distance),
                review_status="pending_administrator_review",
            ))
        return sorted(results, key=lambda item: (
            -item.displacement_score,
            (item.peer_filename or "").casefold(),
            (item.detected_section or "").casefold(),
            item.source_excerpt or "",
        ))

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
        source_payload: Dict, visualization: Dict, narrative: str,
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
        await self._session.commit()
        return await self._load_run(run.id)

    async def _load_run(self, run_id: UUID) -> BenchmarkRun:
        stmt = select(BenchmarkRun).where(BenchmarkRun.id == run_id).options(
            selectinload(BenchmarkRun.white_spaces)
        )
        return (await self._session.execute(stmt)).scalar_one()

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
    def _narrative_prompt(
        white_spaces: Sequence[BenchmarkEvidence], *, scope: str,
        require_administrator_review: bool = False,
    ) -> str:
        rendered = "\n".join(
            f"- {item.domain_label} (displacement={item.displacement_score:.2f}): "
            f"{item.recommendation or 'n/a'}" for item in white_spaces[:10]
        )
        review_boundary = (
            " Do not describe any item as a proven institutional gap; every item "
            "requires administrator review."
            if require_administrator_review else ""
        )
        return (
            "You are an academic strategy analyst. Given the following evidence "
            f"comparing internal faculty capabilities to {scope}, produce a concise "
            f"executive summary.{review_boundary}\n\nEvidence:\n{rendered}"
        )

    @staticmethod
    def _combined_prompt(items: Sequence[Dict]) -> str:
        rendered = "\n".join(
            f"- [{item['source']}] {item['domain_label']} "
            f"(displacement={item['displacement_score']:.2f})" for item in items[:15]
        )
        return (
            "Synthesize global and peer candidate coverage evidence. Do not call any "
            "item a proven institutional gap; administrator review is required. "
            "Limit the response to roughly 300 words.\n\n"
            f"Aggregated evidence:\n{rendered}"
        )
