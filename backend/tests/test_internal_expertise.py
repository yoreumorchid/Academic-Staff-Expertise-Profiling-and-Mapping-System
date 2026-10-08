"""Focused BENCH-01 tests for staff-level internal expertise vectors."""
from __future__ import annotations

import random

import numpy as np

from app.services.internal_expertise import (
    ExpertiseEvidence,
    build_staff_profiles,
    cluster_staff_profiles,
)


def _evidence(
    user: str,
    tag: str,
    vector: list[float] | None,
    *,
    confidence: float,
    validated: bool,
) -> ExpertiseEvidence:
    return ExpertiseEvidence(
        user_id=user,
        user_label=user,
        tag_label=tag,
        embedding=vector,
        confidence=confidence,
        validated=validated,
    )


def test_staff_vector_uses_full_validated_and_confidence_ai_weights() -> None:
    profiles = build_staff_profiles(
        [
            _evidence("u1", "Validated", [1.0, 0.0], confidence=0.1, validated=True),
            _evidence("u1", "Inferred", [0.0, 1.0], confidence=0.7, validated=False),
        ],
        confidence_threshold=0.7,
    )

    assert len(profiles) == 1
    expected = np.asarray([1.0, 0.7])
    expected /= np.linalg.norm(expected)
    assert np.allclose(profiles[0].vector, expected)
    assert profiles[0].tag_weights == (("Validated", 1.0), ("Inferred", 0.7))


def test_staff_vector_filters_low_confidence_and_invalid_embeddings() -> None:
    profiles = build_staff_profiles(
        [
            _evidence("u1", "Keep", [1.0, 0.0], confidence=0.7, validated=False),
            _evidence("u1", "Below", [0.0, 1.0], confidence=0.69, validated=False),
            _evidence("u1", "Missing", None, confidence=1.0, validated=True),
            _evidence("u1", "Zero", [0.0, 0.0], confidence=1.0, validated=True),
            _evidence("u2", "Legacy dimension", [1.0, 0.0, 0.0], confidence=1.0, validated=True),
        ],
        confidence_threshold=0.7,
    )

    assert [profile.user_id for profile in profiles] == ["u1"]
    assert profiles[0].tag_weights == (("Keep", 0.7),)
    assert np.allclose(profiles[0].vector, [1.0, 0.0])


def test_empty_or_insufficient_staff_data_produces_no_clusters() -> None:
    assert build_staff_profiles([]) == []
    two_profiles = build_staff_profiles(
        [
            _evidence("u1", "Alpha", [1.0, 0.0], confidence=1.0, validated=True),
            _evidence("u2", "Beta", [0.0, 1.0], confidence=1.0, validated=True),
        ]
    )
    result = cluster_staff_profiles(two_profiles)
    assert result.selected_k == 0
    assert result.centroids == ()
    assert result.labels == ()


def test_shared_vocabulary_produces_one_observation_per_staff() -> None:
    profiles = build_staff_profiles(
        [
            _evidence(f"u{index}", "Shared AI", [1.0, 0.0], confidence=1.0, validated=True)
            for index in range(5)
        ]
    )

    assert len(profiles) == 5
    assert {profile.user_id for profile in profiles} == {"u0", "u1", "u2", "u3", "u4"}


def test_input_permutation_preserves_user_vector_and_cluster_alignment() -> None:
    evidence = [
        _evidence(f"a{index}", "Alpha", [1.0, 0.01 * index], confidence=1.0, validated=True)
        for index in range(3)
    ] + [
        _evidence(f"b{index}", "Beta", [0.01 * index, 1.0], confidence=1.0, validated=True)
        for index in range(3)
    ]
    baseline_profiles = build_staff_profiles(evidence)
    baseline = cluster_staff_profiles(baseline_profiles)

    shuffled = list(evidence)
    random.Random(27).shuffle(shuffled)
    repeated_profiles = build_staff_profiles(shuffled)
    repeated = cluster_staff_profiles(repeated_profiles)

    assert baseline_profiles == repeated_profiles
    assert baseline.selected_k == repeated.selected_k == 2
    assert baseline.labels == repeated.labels == ("Alpha", "Beta")
    assert baseline.assignments == repeated.assignments
    assert np.allclose(baseline.centroids, repeated.centroids)
