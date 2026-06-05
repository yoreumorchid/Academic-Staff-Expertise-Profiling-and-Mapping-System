"""Stratified-sample publications for human annotation (Study 1 prep).

Usage::

    python -m evaluation.scripts.build_gold_set --n 50 \
        --out evaluation/datasets/_to_annotate.csv

The output CSV has the columns the annotators need (``publication_id``,
``title``, ``abstract``, ``user_full_name``, ``department``) plus two
EMPTY columns (``gold_tags``, ``notes``) for them to fill in.

After two annotators return their CSVs you should merge them into
``datasets/gold_tags.jsonl`` (see ../README.md §1).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import random
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Publication, PublicationAbstract, User
from app.db.session import async_session_factory


async def _fetch_candidates() -> list[tuple[Publication, User, str]]:
    async with async_session_factory() as session:
        stmt = (
            select(Publication)
            .options(selectinload(Publication.user), selectinload(Publication.abstract))
            .where(Publication.abstract_missing.is_(False))
        )
        result = await session.execute(stmt)
        rows: list[tuple[Publication, User, str]] = []
        for pub in result.scalars().all():
            if not pub.abstract or not pub.abstract.abstract_text:
                continue
            if len(pub.abstract.abstract_text) < 200:
                continue
            rows.append((pub, pub.user, pub.abstract.abstract_text))
        return rows


def _stratify(rows, n: int) -> list:
    buckets: dict[str, list] = defaultdict(list)
    for row in rows:
        dept = (row[1].department or "_unknown").strip()
        buckets[dept].append(row)

    rng = random.Random(42)
    per_bucket = max(1, n // max(1, len(buckets)))
    sampled = []
    for dept, items in buckets.items():
        rng.shuffle(items)
        sampled.extend(items[:per_bucket])

    # Fill remainder with random extras if we under-shot.
    if len(sampled) < n:
        remaining = [r for r in rows if r not in sampled]
        rng.shuffle(remaining)
        sampled.extend(remaining[: n - len(sampled)])
    return sampled[:n]


async def main_async(n: int, out: Path) -> None:
    rows = await _fetch_candidates()
    if not rows:
        raise SystemExit("No publications with abstracts found. Run a sync first.")

    sampled = _stratify(rows, n)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "publication_id",
                "title",
                "abstract",
                "user_full_name",
                "department",
                "gold_tags",  # annotator fills in: comma-separated
                "notes",      # annotator fills in: free text (optional)
            ]
        )
        for pub, user, abstract in sampled:
            writer.writerow(
                [
                    str(pub.id),
                    (pub.title or "").strip(),
                    abstract.strip(),
                    user.full_name,
                    user.department or "",
                    "",
                    "",
                ]
            )

    print(f"Wrote {len(sampled)} rows to {out}")
    print("Send this CSV to your annotators. See evaluation/README.md §1.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evaluation/datasets/_to_annotate.csv"),
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.n, args.out))


if __name__ == "__main__":
    main()
