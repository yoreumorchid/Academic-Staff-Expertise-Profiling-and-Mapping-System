"""Study 3 — Aggregate expert Likert ratings for terminology normalization.

Reads ``datasets/expert_review.csv`` (see ../README.md §3) and produces
per-reviewer means, overall preference distribution and an effect-size
estimate.

Usage::

    python -m evaluation.scripts.eval_expert_review \
        --csv evaluation/datasets/expert_review.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

from evaluation.scripts._common import write_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("evaluation/datasets/expert_review.csv"))
    args = parser.parse_args()

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("expert_review.csv is empty.")

    by_reviewer: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_reviewer[r["reviewer_id"]].append(r)

    accuracy_all = [int(r["accuracy"]) for r in rows]
    specificity_all = [int(r["specificity"]) for r in rows]
    pref_counts = Counter(r["preference"].strip().lower() for r in rows)

    pref_normalized_share = pref_counts.get("normalized", 0) / len(rows)

    per_reviewer = {
        rid: {
            "n": len(items),
            "accuracy_mean": round(mean(int(r["accuracy"]) for r in items), 3),
            "specificity_mean": round(mean(int(r["specificity"]) for r in items), 3),
            "pref_normalized_share": round(
                sum(1 for r in items if r["preference"].lower() == "normalized") / len(items),
                3,
            ),
        }
        for rid, items in by_reviewer.items()
    }

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "csv_path": str(args.csv),
        "n_ratings": len(rows),
        "accuracy_mean": round(mean(accuracy_all), 3),
        "accuracy_stdev": round(pstdev(accuracy_all), 3),
        "specificity_mean": round(mean(specificity_all), 3),
        "specificity_stdev": round(pstdev(specificity_all), 3),
        "preference_counts": dict(pref_counts),
        "preference_normalized_share": round(pref_normalized_share, 3),
        "per_reviewer": per_reviewer,
        "passes_acceptance": pref_normalized_share >= 0.75,
    }

    md = (
        "# Terminology Normalization Expert Review\n\n"
        f"* Generated: {payload['generated_at']}\n"
        f"* Ratings: {payload['n_ratings']}\n\n"
        f"| Metric | Mean | Stdev |\n|---|---|---|\n"
        f"| Accuracy (1–5)    | {payload['accuracy_mean']} | {payload['accuracy_stdev']} |\n"
        f"| Specificity (1–5) | {payload['specificity_mean']} | {payload['specificity_stdev']} |\n\n"
        f"Preference distribution: {payload['preference_counts']}\n\n"
        f"Share preferring normalized output: **{payload['preference_normalized_share']:.0%}** "
        f"(target ≥ 75% — {'PASS' if payload['passes_acceptance'] else 'FAIL'})\n"
    )
    json_path, md_path = write_report("expert_review", payload, md)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
