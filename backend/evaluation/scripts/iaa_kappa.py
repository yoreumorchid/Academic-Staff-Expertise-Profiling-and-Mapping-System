"""Cohen's Kappa for two annotators on the same gold-set CSV.

Each CSV must have the columns produced by ``build_gold_set.py`` —
specifically ``publication_id`` and ``gold_tags`` (comma-separated).

Treats the union of all tags either annotator produced as the label
space and computes per-label kappa, then averages.

Usage::

    python -m evaluation.scripts.iaa_kappa \
        --a evaluation/datasets/annotator_A.csv \
        --b evaluation/datasets/annotator_B.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

from evaluation.scripts._common import split_tag_list


def _load(path: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = row["publication_id"].strip()
            tags = set(split_tag_list(row.get("gold_tags", "")))
            out[pid] = tags
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    args = parser.parse_args()

    a = _load(args.a)
    b = _load(args.b)
    shared = sorted(set(a) & set(b))
    if not shared:
        raise SystemExit("Annotator CSVs share no publication_id values.")

    all_tags = set()
    for pid in shared:
        all_tags |= a[pid] | b[pid]
    all_tags = sorted(all_tags)

    y_a, y_b = [], []
    for pid in shared:
        for tag in all_tags:
            y_a.append(1 if tag in a[pid] else 0)
            y_b.append(1 if tag in b[pid] else 0)

    kappa = cohen_kappa_score(y_a, y_b)
    agreement = sum(1 for x, y in zip(y_a, y_b) if x == y) / len(y_a)
    print(f"Publications compared : {len(shared)}")
    print(f"Label space size      : {len(all_tags)}")
    print(f"Raw agreement         : {agreement:.3f}")
    print(f"Cohen's kappa         : {kappa:.3f}")
    if kappa < 0.6:
        print("WARNING: kappa < 0.60 (substantial). Reconcile before treating as gold.")
    else:
        print("OK: kappa >= 0.60.")


if __name__ == "__main__":
    main()
