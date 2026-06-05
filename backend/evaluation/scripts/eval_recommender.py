"""Study 2 — Recommender Top-N accuracy with hybrid / cosine / activation ablation.

Reads ``datasets/gold_recommendations.jsonl`` (one item per line),
invokes :class:`app.services.mapping.MappingService` three times per
item (full hybrid, cosine-only, spreading-only by temporarily zeroing
the other weight) and reports Hit@K, Precision@K, Recall@K, MRR and
nDCG@K.

Usage::

    python -m evaluation.scripts.eval_recommender \
        --gold evaluation/datasets/gold_recommendations.jsonl --k 5
"""
from __future__ import annotations

import argparse
import asyncio
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Sequence
from uuid import UUID

from app.db.models import SpecificationType
from app.db.session import async_session_factory
from app.services import mapping as mapping_module
from app.services.mapping import MappingService
from evaluation.scripts._common import jsonl_lines, write_report


@dataclass
class VariantScore:
    name: str
    hits: list[int] = field(default_factory=list)
    precisions: list[float] = field(default_factory=list)
    recalls: list[float] = field(default_factory=list)
    mrr: list[float] = field(default_factory=list)
    ndcg: list[float] = field(default_factory=list)

    def add(self, ranked_ids: Sequence[str], gold_ids: set[str], k: int) -> None:
        top_k = list(ranked_ids[:k])
        gold_in_topk = [pid for pid in top_k if pid in gold_ids]
        self.hits.append(1 if gold_in_topk else 0)
        self.precisions.append(len(gold_in_topk) / k if k else 0.0)
        self.recalls.append(len(gold_in_topk) / len(gold_ids) if gold_ids else 0.0)

        rr = 0.0
        for idx, pid in enumerate(top_k, start=1):
            if pid in gold_ids:
                rr = 1.0 / idx
                break
        self.mrr.append(rr)

        # nDCG@K with binary relevance.
        dcg = sum(
            (1.0 / math.log2(idx + 1))
            for idx, pid in enumerate(top_k, start=1)
            if pid in gold_ids
        )
        ideal_hits = min(len(gold_ids), k)
        idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
        self.ndcg.append(dcg / idcg if idcg else 0.0)

    def summary(self) -> dict[str, float]:
        return {
            "hit_at_k": round(mean(self.hits), 4) if self.hits else 0.0,
            "precision_at_k": round(mean(self.precisions), 4) if self.precisions else 0.0,
            "recall_at_k": round(mean(self.recalls), 4) if self.recalls else 0.0,
            "mrr": round(mean(self.mrr), 4) if self.mrr else 0.0,
            "ndcg_at_k": round(mean(self.ndcg), 4) if self.ndcg else 0.0,
            "n": len(self.hits),
        }


async def _run_item(
    service: MappingService,
    user_id: UUID,
    item: dict,
    *,
    spec_type: SpecificationType,
) -> dict[str, list[str]]:
    """Return ranked staff-id lists for the three variants."""
    spec = await service.ingest_specification(
        created_by=user_id,
        spec_type=spec_type,
        title=item["title"],
        raw_text=item["raw_text"],
    )

    variants: dict[str, list[str]] = {}

    # Hybrid (default weights).
    report = await service.generate_report(spec_id=spec.id, generated_by=user_id)
    variants["hybrid"] = [str(entry.user_id) for entry in report.entries]

    # Cosine-only: temporarily nuke the spreading weight.
    original_spread = mapping_module.SPREADING_WEIGHT
    original_cos = mapping_module.COSINE_WEIGHT
    try:
        mapping_module.SPREADING_WEIGHT = 0.0
        mapping_module.COSINE_WEIGHT = 1.0
        report = await service.generate_report(spec_id=spec.id, generated_by=user_id)
        variants["cosine_only"] = [str(entry.user_id) for entry in report.entries]

        mapping_module.SPREADING_WEIGHT = 1.0
        mapping_module.COSINE_WEIGHT = 0.0
        report = await service.generate_report(spec_id=spec.id, generated_by=user_id)
        variants["spreading_only"] = [str(entry.user_id) for entry in report.entries]
    finally:
        mapping_module.SPREADING_WEIGHT = original_spread
        mapping_module.COSINE_WEIGHT = original_cos

    return variants


def _markdown(payload: dict) -> str:
    lines = [
        "# Recommender Evaluation Report",
        "",
        f"* Generated: {payload['generated_at']}",
        f"* Gold set: `{payload['gold_path']}` (n={payload['n']})",
        f"* K: {payload['k']}",
        "",
        "| Variant | Hit@K | P@K | R@K | MRR | nDCG@K |",
        "|---|---|---|---|---|---|",
    ]
    for name in ("hybrid", "cosine_only", "spreading_only"):
        s = payload[name]
        lines.append(
            f"| {name} | {s['hit_at_k']} | {s['precision_at_k']} | {s['recall_at_k']} | {s['mrr']} | {s['ndcg_at_k']} |"
        )
    lines.append("")
    h = payload["hybrid"]
    lines.append(
        f"Acceptance: Hit@5 ≥ 0.80 — **{'PASS' if h['hit_at_k'] >= 0.80 else 'FAIL'}**, "
        f"MRR ≥ 0.60 — **{'PASS' if h['mrr'] >= 0.60 else 'FAIL'}**."
    )
    return "\n".join(lines)


async def main_async(gold_path: Path, runner_uuid: UUID, k: int) -> None:
    items = jsonl_lines(gold_path)
    if not items:
        raise SystemExit("Gold recommendations file is empty.")

    variants_scores = {
        "hybrid": VariantScore("hybrid"),
        "cosine_only": VariantScore("cosine_only"),
        "spreading_only": VariantScore("spreading_only"),
    }

    async with async_session_factory() as session:
        service = MappingService(session)
        for item in items:
            spec_type = (
                SpecificationType.GRANT
                if item.get("item_type", "grant") == "grant"
                else SpecificationType.COURSE
            )
            gold_ids = set(item["expert_picks"])
            ranked = await _run_item(service, runner_uuid, item, spec_type=spec_type)
            for name, score in variants_scores.items():
                score.add(ranked.get(name, []), gold_ids, k)

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "gold_path": str(gold_path),
        "n": len(items),
        "k": k,
        "hybrid": variants_scores["hybrid"].summary(),
        "cosine_only": variants_scores["cosine_only"].summary(),
        "spreading_only": variants_scores["spreading_only"].summary(),
    }
    json_path, md_path = write_report("recommender", payload, _markdown(payload))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold",
        type=Path,
        default=Path("evaluation/datasets/gold_recommendations.jsonl"),
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--runner-uuid",
        type=UUID,
        required=True,
        help="UUID of an existing admin/FA user used as the spec's created_by.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.gold, args.runner_uuid, args.k))


if __name__ == "__main__":
    main()
