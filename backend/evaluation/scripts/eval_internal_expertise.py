"""BENCH-01 parameter sensitivity for staff-level expertise clustering.

This DB-independent study uses deterministic labelled synthetic faculties. It
is intended to detect unstable or clearly unsuitable parameter choices before
running the same production functions on real data. It is not external
validation of real faculty clusters.

Run from ``backend/``::

    python -m evaluation.scripts.eval_internal_expertise
"""
from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime

import numpy as np
from sklearn.metrics import adjusted_rand_score

from app.services.internal_expertise import (
    ExpertiseEvidence,
    build_staff_profiles,
    cluster_staff_profiles,
)
from evaluation.scripts._common import write_report


def _fixture(group_count: int, *, seed: int) -> tuple[list[ExpertiseEvidence], dict[str, int]]:
    """Create separable staff groups with uncertain correct and noisy links."""
    rng = np.random.default_rng(seed)
    evidence: list[ExpertiseEvidence] = []
    truth: dict[str, int] = {}
    dimension = group_count + 2

    for group in range(group_count):
        basis = np.zeros(dimension)
        basis[group] = 1.0
        noisy_basis = np.zeros(dimension)
        noisy_basis[(group + 1) % group_count] = 1.0
        for member in range(6):
            user_id = f"g{group}-staff-{member}"
            truth[user_id] = group
            correct = basis + rng.normal(0.0, 0.035, dimension)
            secondary = basis + rng.normal(0.0, 0.06, dimension)

            # Four profiles contain human-confirmed evidence. Two exercise the
            # confidence threshold and its staff-coverage trade-off.
            if member < 4:
                evidence.append(
                    ExpertiseEvidence(
                        user_id,
                        user_id,
                        f"Domain {group} core",
                        correct,
                        0.45 + member * 0.1,
                        True,
                    )
                )
            else:
                evidence.append(
                    ExpertiseEvidence(
                        user_id,
                        user_id,
                        f"Domain {group} inferred",
                        correct,
                        0.62 if member == 4 else 0.74,
                        False,
                    )
                )

            evidence.append(
                ExpertiseEvidence(
                    user_id,
                    user_id,
                    f"Domain {group} secondary",
                    secondary,
                    0.82,
                    member % 2 == 0,
                )
            )
            evidence.append(
                ExpertiseEvidence(
                    user_id,
                    user_id,
                    f"Noise toward {(group + 1) % group_count}",
                    noisy_basis + rng.normal(0.0, 0.04, dimension),
                    0.52 + 0.04 * (member % 4),
                    False,
                )
            )
    # Exercise missing, zero, and inconsistent embeddings without changing truth.
    evidence.extend(
        [
            ExpertiseEvidence("invalid-none", "invalid-none", "missing", None, 1.0, True),
            ExpertiseEvidence("invalid-zero", "invalid-zero", "zero", [0.0] * dimension, 1.0, True),
            ExpertiseEvidence("invalid-dim", "invalid-dim", "legacy", [1.0, 0.0], 1.0, True),
        ]
    )
    return evidence, truth


def _evaluate_setting(threshold: float, max_clusters: int, n_init: int) -> dict:
    scenarios: list[dict] = []
    for group_count, seed in ((3, 1303), (6, 1606)):
        evidence, truth = _fixture(group_count, seed=seed)
        profiles = build_staff_profiles(evidence, confidence_threshold=threshold)
        result = cluster_staff_profiles(
            profiles,
            max_clusters=max_clusters,
            n_init=n_init,
        )
        predicted = dict(result.assignments)
        included = sorted(set(truth) & set(predicted))
        ari = (
            adjusted_rand_score(
                [truth[user_id] for user_id in included],
                [predicted[user_id] for user_id in included],
            )
            if included
            else 0.0
        )

        stability_scores: list[float] = []
        for permutation_seed in range(5):
            shuffled = list(evidence)
            random.Random(permutation_seed).shuffle(shuffled)
            repeated = cluster_staff_profiles(
                build_staff_profiles(shuffled, confidence_threshold=threshold),
                max_clusters=max_clusters,
                n_init=n_init,
            )
            repeated_map = dict(repeated.assignments)
            common = sorted(set(predicted) & set(repeated_map))
            stability_scores.append(
                adjusted_rand_score(
                    [predicted[user_id] for user_id in common],
                    [repeated_map[user_id] for user_id in common],
                )
                if common
                else 0.0
            )
        scenarios.append(
            {
                "reference_groups": group_count,
                "staff_count": len(truth),
                "included_staff": len(included),
                "coverage": len(included) / len(truth),
                "selected_k": result.selected_k,
                "ari": float(ari),
                "silhouette": float(result.silhouette or 0.0),
                "permutation_stability": float(np.mean(stability_scores)),
            }
        )

    means = {
        key: float(np.mean([scenario[key] for scenario in scenarios]))
        for key in ("coverage", "ari", "silhouette", "permutation_stability")
    }
    # ARI is primary; coverage guards against achieving purity by discarding
    # uncertain profiles. Silhouette and permutation stability are supporting
    # checks. The weighting is fixed before examining the grid results.
    selection_score = (
        0.45 * max(0.0, means["ari"])
        + 0.25 * means["coverage"]
        + 0.20 * ((means["silhouette"] + 1.0) / 2.0)
        + 0.10 * means["permutation_stability"]
    )
    return {
        "confidence_threshold": threshold,
        "max_clusters": max_clusters,
        "n_init": n_init,
        "selection_score": float(selection_score),
        "mean_metrics": means,
        "scenarios": scenarios,
    }


def _markdown(payload: dict) -> str:
    rows = "\n".join(
        "| {confidence_threshold:.2f} | {max_clusters} | {n_init} | "
        "{mean_metrics[ari]:.4f} | {mean_metrics[silhouette]:.4f} | "
        "{mean_metrics[coverage]:.4f} | {mean_metrics[permutation_stability]:.4f} | "
        "{selection_score:.4f} |".format(**row)
        for row in payload["results"]
    )
    selected = payload["selected"]
    return f"""# BENCH-01 Internal Expertise Parameter Evaluation

Generated: {payload['generated_at']}

## Scope and limitation

This DB-independent sensitivity run uses two deterministic synthetic faculties
with three and six known expertise groups. It checks parameter behaviour,
coverage, vector/input alignment, and reproducibility. It does **not** establish
that clusters found in real faculty data are externally valid; representative
real profiles and peer documents remain a BENCH-03 requirement.

## Fixed selection rule

`score = 0.45 * ARI + 0.25 * coverage + 0.20 * normalized silhouette + 0.10 * stability`

ARI is agreement with the fixture's known groups. Coverage prevents a setting
from looking accurate by excluding uncertain staff. Stability is ARI between
the baseline result and five input permutations. Ties prefer lower threshold,
smaller cluster cap, then fewer initializations.

| tau | K_max | n_init | mean ARI | mean silhouette | coverage | stability | score |
|---:|---:|---:|---:|---:|---:|---:|---:|
{rows}

## Selected parameters

- `tau = {selected['confidence_threshold']}`
- `K_max = {selected['max_clusters']}`
- `n_init = {selected['n_init']}`
- selection score = `{selected['selection_score']:.4f}`

The companion JSON contains per-scenario metrics for every tested setting.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thresholds", default="0.50,0.60,0.70,0.80")
    parser.add_argument("--max-clusters", default="3,4,5,6")
    parser.add_argument("--n-init", default="10,20")
    args = parser.parse_args()

    thresholds = [float(value) for value in args.thresholds.split(",")]
    max_clusters = [int(value) for value in args.max_clusters.split(",")]
    initializations = [int(value) for value in args.n_init.split(",")]
    results = [
        _evaluate_setting(threshold, cluster_cap, initialization_count)
        for threshold in thresholds
        for cluster_cap in max_clusters
        for initialization_count in initializations
    ]
    results.sort(
        key=lambda row: (
            -row["selection_score"],
            row["confidence_threshold"],
            row["max_clusters"],
            row["n_init"],
        )
    )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "fixture": "deterministic synthetic faculties with 3 and 6 reference groups",
        "selection_formula": (
            "0.45*ARI + 0.25*coverage + 0.20*((silhouette+1)/2) + 0.10*stability"
        ),
        "selected": results[0],
        "results": results,
    }
    json_path, markdown_path = write_report(
        "internal_expertise_tuning", payload, _markdown(payload)
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(
        "Selected: tau={confidence_threshold}, K_max={max_clusters}, "
        "n_init={n_init}, score={selection_score:.4f}".format(**results[0])
    )


if __name__ == "__main__":
    main()
