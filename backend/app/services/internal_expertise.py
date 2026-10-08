"""Deterministic staff-level expertise vectors and clustering for BENCH-01."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Hashable, Iterable, Sequence

import numpy as np


DEFAULT_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_MAX_CLUSTERS = 6
DEFAULT_KMEANS_N_INIT = 10
DEFAULT_RANDOM_STATE = 42


@dataclass(frozen=True)
class ExpertiseEvidence:
    """One staff-to-tag link after database eligibility filtering."""

    user_id: Hashable
    user_label: str
    tag_label: str
    embedding: Sequence[float] | None
    confidence: float
    validated: bool


@dataclass(frozen=True)
class StaffExpertiseProfile:
    """One normalized staff vector plus the evidence used to label clusters."""

    user_id: Hashable
    user_label: str
    vector: tuple[float, ...]
    tag_weights: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class StaffClusterResult:
    centroids: tuple[tuple[float, ...], ...] = ()
    labels: tuple[str, ...] = ()
    assignments: tuple[tuple[Hashable, int], ...] = ()
    selected_k: int = 0
    silhouette: float | None = None


def build_staff_profiles(
    evidence: Iterable[ExpertiseEvidence],
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[StaffExpertiseProfile]:
    """Build one weighted, L2-normalized vector per staff member.

    Validated links receive full weight. Unvalidated links must meet the
    threshold and are weighted by their clamped confidence. Invalid, zero, and
    minority-dimension embeddings are omitted so vector rows stay aligned.
    """
    usable: list[tuple[ExpertiseEvidence, np.ndarray, float]] = []
    dimension_counts: Counter[int] = Counter()

    for item in evidence:
        confidence = min(1.0, max(0.0, float(item.confidence or 0.0)))
        if not item.validated and confidence < confidence_threshold:
            continue
        weight = 1.0 if item.validated else confidence
        if weight <= 0.0 or item.embedding is None:
            continue
        try:
            vector = np.asarray(item.embedding, dtype=float)
        except (TypeError, ValueError):
            continue
        if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
            continue
        norm = float(np.linalg.norm(vector))
        if not isfinite(norm) or norm == 0.0:
            continue
        normalized = vector / norm
        usable.append((item, normalized, weight))
        dimension_counts[int(vector.size)] += 1

    if not dimension_counts:
        return []
    # Existing rows should share one model dimension. Majority selection keeps a
    # single malformed/legacy row from discarding the otherwise valid cohort.
    target_dimension = min(
        dimension_counts,
        key=lambda size: (-dimension_counts[size], size),
    )

    grouped: dict[Hashable, list[tuple[ExpertiseEvidence, np.ndarray, float]]] = (
        defaultdict(list)
    )
    for item, vector, weight in usable:
        if vector.size == target_dimension:
            grouped[item.user_id].append((item, vector, weight))

    profiles: list[StaffExpertiseProfile] = []
    for user_id in sorted(grouped, key=str):
        rows = sorted(grouped[user_id], key=lambda row: row[0].tag_label.casefold())
        total_weight = sum(weight for _, _, weight in rows)
        if total_weight <= 0.0:
            continue
        raw = sum((weight * vector for _, vector, weight in rows), np.zeros(target_dimension))
        raw /= total_weight
        norm = float(np.linalg.norm(raw))
        if not isfinite(norm) or norm == 0.0:
            continue

        tag_weights: dict[str, float] = defaultdict(float)
        for item, _, weight in rows:
            tag_weights[item.tag_label] += weight
        profiles.append(
            StaffExpertiseProfile(
                user_id=user_id,
                user_label=rows[0][0].user_label,
                vector=tuple(float(value) for value in raw / norm),
                tag_weights=tuple(
                    sorted(tag_weights.items(), key=lambda pair: (-pair[1], pair[0].casefold()))
                ),
            )
        )
    return profiles


def cluster_staff_profiles(
    profiles: Sequence[StaffExpertiseProfile],
    *,
    max_clusters: int = DEFAULT_MAX_CLUSTERS,
    n_init: int = DEFAULT_KMEANS_N_INIT,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> StaffClusterResult:
    """Select ``k`` by cosine silhouette and cluster stable staff rows."""
    ordered = sorted(profiles, key=lambda profile: str(profile.user_id))
    if len(ordered) < 3:
        return StaffClusterResult()

    matrix = np.asarray([profile.vector for profile in ordered], dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        return StaffClusterResult()
    distinct_count = len(np.unique(matrix, axis=0))
    candidate_max = min(max_clusters, len(ordered) - 1, distinct_count)
    if candidate_max < 2:
        return StaffClusterResult()

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    best_model: KMeans | None = None
    best_assignments: np.ndarray | None = None
    best_score = float("-inf")
    for candidate_k in range(2, candidate_max + 1):
        model = KMeans(
            n_clusters=candidate_k,
            init="k-means++",
            n_init=n_init,
            random_state=random_state,
        )
        assignments = model.fit_predict(matrix)
        if len(set(int(value) for value in assignments)) < 2:
            continue
        score = float(silhouette_score(matrix, assignments, metric="cosine"))
        # Iteration is ascending, so an exact tie intentionally keeps smaller k.
        if score > best_score + 1e-12:
            best_model = model
            best_assignments = assignments
            best_score = score

    if best_model is None or best_assignments is None:
        return StaffClusterResult()

    clusters: list[tuple[str, tuple[float, ...], int]] = []
    for original_index, centroid in enumerate(best_model.cluster_centers_):
        member_indexes = [
            index
            for index, assignment in enumerate(best_assignments)
            if int(assignment) == original_index
        ]
        tag_totals: dict[str, float] = defaultdict(float)
        for member_index in member_indexes:
            for tag, weight in ordered[member_index].tag_weights:
                tag_totals[tag] += weight
        top_tags = sorted(
            tag_totals.items(), key=lambda pair: (-pair[1], pair[0].casefold())
        )[:3]
        label = " / ".join(tag for tag, _ in top_tags) or f"Cluster {original_index + 1}"
        centroid_norm = float(np.linalg.norm(centroid))
        normalized_centroid = centroid / centroid_norm if centroid_norm else centroid
        clusters.append(
            (
                label,
                tuple(float(value) for value in normalized_centroid),
                original_index,
            )
        )

    clusters.sort(key=lambda item: (item[0].casefold(), item[1]))
    remap = {original: new for new, (_, _, original) in enumerate(clusters)}
    assignment_rows = tuple(
        (profile.user_id, remap[int(assignment)])
        for profile, assignment in zip(ordered, best_assignments)
    )
    return StaffClusterResult(
        centroids=tuple(centroid for _, centroid, _ in clusters),
        labels=tuple(label for label, _, _ in clusters),
        assignments=assignment_rows,
        selected_k=len(clusters),
        silhouette=best_score,
    )
