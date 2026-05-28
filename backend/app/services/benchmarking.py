"""Gap analytics & benchmarking engine (UC-15, UC-16, UC-17).

Combines:

* **K-Means clustering** of internal faculty expertise embeddings.
* **Global benchmarking** — fetches IEEE Xplore frontier publications,
  embeds them, and computes centroid displacement.
* **Peer benchmarking** — accepts manually uploaded curriculum
  documents, extracts text via :mod:`document_extract`, and performs the
  same displacement analysis.
* **UMAP dimensionality reduction** — projects the high-dimensional
  centroids into a 2-D scatter payload for the frontend.
* **LLM narrative synthesis** — turns the numeric gap into prose.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ExternalServiceError, ValidationFailure
from app.db.models import (
    BenchmarkRun,
    BenchmarkType,
    BenchmarkWhiteSpace,
    ExpertiseTag,
    UserExpertiseTag,
)
from app.services.embeddings import embed_text, embed_texts
from app.services.external_apis import IeeeXploreClient
from app.services.llm_normalize import synthesize_narrative

logger = logging.getLogger(__name__)

# Tunables — kept conservative to make the pipeline runnable with a
# small faculty (the spec doesn't pin specific values for these).
DEFAULT_CLUSTER_COUNT = 6
GLOBAL_QUERIES: Tuple[str, ...] = (
    "artificial intelligence",
    "machine learning",
    "quantum computing",
    "renewable energy systems",
    "biotechnology",
    "cybersecurity",
    "sustainable engineering",
    "data science",
)


class BenchmarkingService:
    """High-level orchestration for the gap analytics module."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._ieee = IeeeXploreClient()

    # ------------------------------------------------------------------ UC-15
    async def run_global_benchmark(self, *, triggered_by: UUID) -> BenchmarkRun:
        internal_centroids, internal_labels = await self._cluster_internal_expertise()
        if not internal_centroids:
            raise ValidationFailure(
                "Insufficient internal expertise data to compare against global trends. "
                "Trigger an expertise sync first.",
            )

        global_vectors, global_labels = await self._fetch_global_vectors()
        white_spaces = self._compute_white_spaces(
            internal_centroids, internal_labels, global_vectors, global_labels
        )
        visualization = self._build_visualization_payload(
            internal_centroids, internal_labels, global_vectors, global_labels
        )

        narrative = await synthesize_narrative(
            self._narrative_prompt(white_spaces, scope="global research frontiers")
        )

        return await self._persist_run(
            triggered_by=triggered_by,
            benchmark_type=BenchmarkType.GLOBAL,
            source_payload={"queries": list(GLOBAL_QUERIES)},
            visualization=visualization,
            narrative=narrative,
            white_spaces=white_spaces,
        )

    # ------------------------------------------------------------------ UC-16
    async def run_peer_benchmark(
        self, *, triggered_by: UUID, peer_documents: List[Tuple[str, str]]
    ) -> BenchmarkRun:
        """``peer_documents`` is a list of ``(filename, extracted_text)``."""
        if not peer_documents:
            raise ValidationFailure(
                "Upload at least one peer curriculum document to benchmark against."
            )

        internal_centroids, internal_labels = await self._cluster_internal_expertise()
        if not internal_centroids:
            raise ValidationFailure(
                "Insufficient internal expertise data to compare against peers. "
                "Trigger an expertise sync first.",
            )

        # Each document contributes one or more text blocks; we treat the
        # full document as a single competency vector for simplicity.
        peer_texts = [text for _, text in peer_documents if text.strip()]
        if not peer_texts:
            raise ValidationFailure(
                "Could not identify meaningful academic domains in the uploads."
            )
        peer_vectors = await embed_texts(peer_texts)
        peer_labels = [name for name, _ in peer_documents][: len(peer_vectors)]

        white_spaces = self._compute_white_spaces(
            internal_centroids, internal_labels, peer_vectors, peer_labels
        )
        visualization = self._build_visualization_payload(
            internal_centroids, internal_labels, peer_vectors, peer_labels
        )
        narrative = await synthesize_narrative(
            self._narrative_prompt(white_spaces, scope="peer institutional curricula")
        )

        return await self._persist_run(
            triggered_by=triggered_by,
            benchmark_type=BenchmarkType.PEER,
            source_payload={"documents": peer_labels},
            visualization=visualization,
            narrative=narrative,
            white_spaces=white_spaces,
        )

    # ------------------------------------------------------------------ UC-17
    async def generate_combined_report(self, *, triggered_by: UUID) -> Dict:
        """Aggregate the most recent global and peer runs into one payload."""
        latest_global = await self._latest_run(BenchmarkType.GLOBAL)
        latest_peer = await self._latest_run(BenchmarkType.PEER)
        if latest_global is None and latest_peer is None:
            raise ValidationFailure(
                "No benchmark runs are available. Execute a global or peer "
                "benchmark first.",
            )

        combined_spaces: List[Dict] = []
        for run in (latest_global, latest_peer):
            if run is None:
                continue
            for space in run.white_spaces:
                combined_spaces.append(
                    {
                        "source": run.benchmark_type.value,
                        "domain_label": space.domain_label,
                        "displacement_score": space.displacement_score,
                        "recommendation": space.recommendation,
                    }
                )

        narrative = await synthesize_narrative(
            self._combined_prompt(combined_spaces)
        )
        return {
            "narrative": narrative,
            "white_spaces": combined_spaces,
            "global_run_id": str(latest_global.id) if latest_global else None,
            "peer_run_id": str(latest_peer.id) if latest_peer else None,
        }

    # ------------------------------------------------------------------ Internal
    async def _cluster_internal_expertise(
        self,
    ) -> Tuple[List[List[float]], List[str]]:
        """Run K-Means on every persisted expertise tag embedding."""
        stmt = select(ExpertiseTag).where(ExpertiseTag.embedding.isnot(None))
        rows = list((await self._session.execute(stmt)).scalars().all())
        embeddings = [row.embedding for row in rows if row.embedding]
        if len(embeddings) < 2:
            return [], []

        from sklearn.cluster import KMeans

        n_clusters = max(2, min(DEFAULT_CLUSTER_COUNT, len(embeddings)))
        matrix = np.asarray(embeddings, dtype=float)
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        assignments = km.fit_predict(matrix)
        centroids = km.cluster_centers_.tolist()

        # Label each cluster with the canonical tag closest to its centroid.
        labels: List[str] = []
        for idx, centroid in enumerate(km.cluster_centers_):
            cluster_members = [
                rows[i] for i, a in enumerate(assignments) if a == idx
            ]
            if not cluster_members:
                labels.append(f"Cluster {idx + 1}")
                continue
            best = min(
                cluster_members,
                key=lambda r: float(
                    np.linalg.norm(np.asarray(r.embedding) - centroid)
                ),
            )
            labels.append(best.canonical_label)
        return centroids, labels

    async def _fetch_global_vectors(self) -> Tuple[List[List[float]], List[str]]:
        """Pull IEEE Xplore titles and embed them as the global frontier set."""
        snippets: List[str] = []
        for query in GLOBAL_QUERIES:
            try:
                payload = await self._ieee.search(query, max_records=10)
            except ExternalServiceError:
                logger.warning("IEEE Xplore query failed for %s — skipping", query)
                continue
            for article in payload.get("articles", []) or []:
                title = (article.get("title") or "").strip()
                abstract = (article.get("abstract") or "").strip()
                blob = f"{title}. {abstract}".strip(". ")
                if len(blob) >= 30:
                    snippets.append(blob)
        if not snippets:
            raise ExternalServiceError(
                "IEEE Xplore did not return any benchmark records.",
            )
        vectors = await embed_texts(snippets)
        return vectors, [s[:120] for s in snippets]

    @staticmethod
    def _compute_white_spaces(
        internal_centroids: Sequence[Sequence[float]],
        internal_labels: Sequence[str],
        external_vectors: Sequence[Sequence[float]],
        external_labels: Sequence[str],
    ) -> List[Tuple[str, float, Optional[str]]]:
        """For each external concept, distance to its nearest internal centroid."""
        if not internal_centroids or not external_vectors:
            return []
        internal = np.asarray(internal_centroids, dtype=float)
        results: List[Tuple[str, float, Optional[str]]] = []
        for label, vector in zip(external_labels, external_vectors):
            v = np.asarray(vector, dtype=float)
            # Cosine distance to nearest internal centroid.
            num = internal @ v
            den = np.linalg.norm(internal, axis=1) * np.linalg.norm(v)
            den[den == 0.0] = 1e-12
            similarities = num / den
            best_idx = int(np.argmax(similarities))
            displacement = float(1.0 - similarities[best_idx])
            recommendation = (
                f"Closest internal cluster: '{internal_labels[best_idx]}'."
                if internal_labels
                else None
            )
            results.append((label, displacement, recommendation))
        # Surface the widest gaps first.
        results.sort(key=lambda r: r[1], reverse=True)
        return results[:25]

    @staticmethod
    def _build_visualization_payload(
        internal_centroids: Sequence[Sequence[float]],
        internal_labels: Sequence[str],
        external_vectors: Sequence[Sequence[float]],
        external_labels: Sequence[str],
    ) -> Dict:
        """Project all points into 2D via UMAP for the dashboard scatter plot."""
        combined = list(internal_centroids) + list(external_vectors)
        if len(combined) < 3:
            return {"points": []}
        matrix = np.asarray(combined, dtype=float)
        try:
            import umap  # type: ignore

            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=min(5, len(matrix) - 1),
                random_state=42,
                metric="cosine",
            )
            coords = reducer.fit_transform(matrix)
        except Exception:  # noqa: BLE001 — fall back to PCA on convergence failure.
            logger.exception("UMAP projection failed; falling back to PCA")
            from sklearn.decomposition import PCA

            coords = PCA(n_components=2, random_state=42).fit_transform(matrix)

        points: List[Dict] = []
        cutoff = len(internal_centroids)
        for idx, (x, y) in enumerate(coords):
            label = (
                internal_labels[idx]
                if idx < cutoff
                else external_labels[idx - cutoff]
            )
            points.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "label": label,
                    "kind": "internal" if idx < cutoff else "external",
                }
            )
        return {"points": points}

    async def _persist_run(
        self,
        *,
        triggered_by: UUID,
        benchmark_type: BenchmarkType,
        source_payload: Dict,
        visualization: Dict,
        narrative: str,
        white_spaces: List[Tuple[str, float, Optional[str]]],
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
        for label, displacement, recommendation in white_spaces:
            self._session.add(
                BenchmarkWhiteSpace(
                    run_id=run.id,
                    domain_label=label,
                    displacement_score=displacement,
                    recommendation=recommendation,
                )
            )
        await self._session.commit()
        return await self._load_run(run.id)

    async def _load_run(self, run_id: UUID) -> BenchmarkRun:
        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.id == run_id)
            .options(selectinload(BenchmarkRun.white_spaces))
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
        white_spaces: Sequence[Tuple[str, float, Optional[str]]], *, scope: str
    ) -> str:
        rendered = "\n".join(
            f"- {label} (displacement={displacement:.2f}): {rec or 'n/a'}"
            for label, displacement, rec in white_spaces[:10]
        )
        return (
            "You are an academic strategy analyst. Given the following "
            f"gap data points comparing internal faculty capabilities to {scope}, "
            "produce a concise (200-300 word) executive summary highlighting "
            "the most significant white spaces and recommending strategic "
            "actions (recruitment, curriculum updates, partnerships).\n\n"
            f"Gap data:\n{rendered}"
        )

    @staticmethod
    def _combined_prompt(items: Sequence[Dict]) -> str:
        rendered = "\n".join(
            f"- [{item['source']}] {item['domain_label']} "
            f"(displacement={item['displacement_score']:.2f})"
            for item in items[:15]
        )
        return (
            "Synthesize a combined gap analysis report integrating both "
            "global research frontiers and peer institutional curricula. "
            "Identify cross-cutting blind spots and prioritized recommendations. "
            "Limit the response to roughly 300 words.\n\n"
            f"Aggregated gaps:\n{rendered}"
        )
