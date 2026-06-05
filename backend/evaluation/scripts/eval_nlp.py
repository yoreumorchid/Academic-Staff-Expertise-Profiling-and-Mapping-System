"""Study 1 — NLP tag-extraction precision / recall / F1 with ablation.

Runs the **same** publications through two pipelines:

* ``scibert``     — :func:`app.services.nlp_pipeline.extract_keywords`
* ``scibert_llm`` — SciBERT followed by
                   :func:`app.services.llm_normalize.normalize_keywords`

and compares both against ``datasets/gold_tags.jsonl``.

Reports per-pipeline macro Precision@K, Recall@K, F1 (hard match) and
F1 (soft match — token-set fuzzy ≥ 85). Writes a JSON + Markdown pair
under ``reports/``.

Database independence
---------------------
The default run mode is **completely DB-independent**: the script reads
the title + abstract text directly from ``gold_tags.jsonl`` and pipes
them through the production NLP functions. It will run even with an
empty ``publications`` table — perfect for the solo-developer phase
where the gold set is curated by hand on Google Scholar / OpenAlex
(see ``prepare_data.py``).

The optional ``--emit-pairs`` side-mode DOES touch the DB (it samples
20 existing users for Study 3 prep). Do not pass that flag until the
DB has been seeded with real harvested data.

Usage
-----
::

    # Default (Top-10 metrics)
    python -m evaluation.scripts.eval_nlp \
        --gold evaluation/datasets/gold_tags.jsonl

    # Stricter Top-5 metrics — recommended while gold set is small.
    python -m evaluation.scripts.eval_nlp \
        --gold evaluation/datasets/gold_tags.jsonl --k 5
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Sequence

from rapidfuzz import fuzz

from app.services.llm_normalize import normalize_keywords
from app.services.nlp_pipeline import extract_keywords
from evaluation.scripts._common import (
    canonicalise,
    f1,
    jsonl_lines,
    write_report,
)

SOFT_THRESHOLD = 85  # rapidfuzz token_set_ratio


@dataclass
class PipelineScore:
    name: str
    precisions: list[float] = field(default_factory=list)
    recalls: list[float] = field(default_factory=list)
    soft_precisions: list[float] = field(default_factory=list)
    soft_recalls: list[float] = field(default_factory=list)

    def add(self, predicted: Sequence[str], gold: Sequence[str]) -> None:
        p_set = set(canonicalise(t) for t in predicted if t)
        g_set = set(canonicalise(t) for t in gold if t)
        if not p_set and not g_set:
            return
        tp = len(p_set & g_set)
        self.precisions.append(tp / len(p_set) if p_set else 0.0)
        self.recalls.append(tp / len(g_set) if g_set else 0.0)

        # Soft match: a predicted tag counts as TP if it fuzzy-matches
        # any gold tag at >= SOFT_THRESHOLD.
        soft_tp_p = sum(
            1
            for p in p_set
            if any(fuzz.token_set_ratio(p, g) >= SOFT_THRESHOLD for g in g_set)
        )
        soft_tp_r = sum(
            1
            for g in g_set
            if any(fuzz.token_set_ratio(g, p) >= SOFT_THRESHOLD for p in p_set)
        )
        self.soft_precisions.append(soft_tp_p / len(p_set) if p_set else 0.0)
        self.soft_recalls.append(soft_tp_r / len(g_set) if g_set else 0.0)

    def summary(self) -> dict[str, float]:
        p = mean(self.precisions) if self.precisions else 0.0
        r = mean(self.recalls) if self.recalls else 0.0
        sp = mean(self.soft_precisions) if self.soft_precisions else 0.0
        sr = mean(self.soft_recalls) if self.soft_recalls else 0.0
        return {
            "precision_hard": round(p, 4),
            "recall_hard": round(r, 4),
            "f1_hard": round(f1(p, r), 4),
            "precision_soft": round(sp, 4),
            "recall_soft": round(sr, 4),
            "f1_soft": round(f1(sp, sr), 4),
            "n": len(self.precisions),
        }


async def _run_pipelines(
    abstracts: list[tuple[str, str, list[str]]],
    k: int,
    pairs_writer: csv.writer | None,
) -> tuple[PipelineScore, PipelineScore]:
    scibert = PipelineScore("scibert_only")
    fused = PipelineScore("scibert_plus_llm")

    for pub_id, abstract, gold in abstracts:
        raw = await extract_keywords(abstract, top_k=k)
        raw_terms = [phrase for phrase, _ in raw]
        scibert.add(raw_terms, gold)

        try:
            normalized = await normalize_keywords(raw_terms)
            norm_terms = [t.canonical_label for t in normalized]
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] LLM normalize failed for {pub_id}: {exc}")
            norm_terms = raw_terms
        fused.add(norm_terms, gold)

        if pairs_writer is not None:
            pairs_writer.writerow(
                [pub_id, "; ".join(raw_terms), "; ".join(norm_terms), "; ".join(gold)]
            )

    return scibert, fused


def _markdown(payload: dict) -> str:
    s_a = payload["scibert_only"]
    s_b = payload["scibert_plus_llm"]
    return f"""# NLP Evaluation Report

* Generated: {payload['generated_at']}
* Gold set: `{payload['gold_path']}` (n={payload['n']})
* K (top-K predictions): {payload['k']}

| Pipeline | P (hard) | R (hard) | F1 (hard) | P (soft) | R (soft) | F1 (soft) |
|---|---|---|---|---|---|---|
| SciBERT only        | {s_a['precision_hard']} | {s_a['recall_hard']} | **{s_a['f1_hard']}** | {s_a['precision_soft']} | {s_a['recall_soft']} | **{s_a['f1_soft']}** |
| SciBERT + LLM refine | {s_b['precision_hard']} | {s_b['recall_hard']} | **{s_b['f1_hard']}** | {s_b['precision_soft']} | {s_b['recall_soft']} | **{s_b['f1_soft']}** |

Acceptance thresholds:

* Hard-match F1 ≥ 0.85 — {'PASS' if s_b['f1_hard'] >= 0.85 else 'FAIL'}
* Soft-match F1 ≥ 0.90 — {'PASS' if s_b['f1_soft'] >= 0.90 else 'FAIL'}
"""


async def main_async(gold_path: Path, k: int, pairs_path: Path | None) -> None:
    gold = jsonl_lines(gold_path)
    abstracts = [
        (row["publication_id"], row["abstract"], row.get("gold_tags", []))
        for row in gold
        if row.get("abstract") and row.get("gold_tags")
    ]
    if not abstracts:
        raise SystemExit("Gold file has no usable rows.")

    pairs_fh = None
    pairs_writer = None
    if pairs_path is not None:
        pairs_path.parent.mkdir(parents=True, exist_ok=True)
        pairs_fh = pairs_path.open("w", encoding="utf-8", newline="")
        pairs_writer = csv.writer(pairs_fh)
        pairs_writer.writerow(["publication_id", "raw_keywords", "normalized_tags", "gold_tags"])

    try:
        scibert, fused = await _run_pipelines(abstracts, k, pairs_writer)
    finally:
        if pairs_fh is not None:
            pairs_fh.close()

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "gold_path": str(gold_path),
        "n": len(abstracts),
        "k": k,
        "scibert_only": scibert.summary(),
        "scibert_plus_llm": fused.summary(),
    }
    json_path, md_path = write_report("nlp", payload, _markdown(payload))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if pairs_path is not None:
        print(f"Wrote pair table {pairs_path} — feed this into the Study 3 review.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path("evaluation/datasets/gold_tags.jsonl"))
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument(
        "--emit-pairs",
        type=Path,
        default=None,
        help="Optional CSV to dump (raw, normalized, gold) triples.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.gold, args.k, args.emit_pairs))


if __name__ == "__main__":
    main()
"""Study 1 — NLP tag-extraction evaluation (SciBERT vs SciBERT+LLM).

Reads ``datasets/gold_tags.jsonl`` and runs each abstract through:

* Run A: ``nlp_pipeline.extract_keywords`` only (SciBERT-only).
* Run B: SciBERT then ``llm_normalize.normalize_keywords`` (full pipeline).

Reports per-publication and macro-averaged Precision@K, Recall@K, F1
under both **hard match** (canonical-string equality) and **soft match**
(embedding cosine >= 0.80) at K = 5, 10, and "all predicted".

Usage::

    python -m evaluation.scripts.eval_nlp \
        --gold evaluation/datasets/gold_tags.jsonl \
        --k 10

Side modes::

    --emit-pairs evaluation/datasets/raw_vs_normalized.csv
        Skip metric computation; just dump the (raw, normalized) pairs
        for 20 random staff so you can prepare the expert-review study.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from statistics import mean
from typing import Sequence

from app.services.embeddings import cosine_similarity, embed_text
from app.services.llm_normalize import normalize_keywords
from app.services.nlp_pipeline import extract_keywords

from evaluation.scripts._common import (
    canonicalise,
    f1,
    jsonl_lines,
    write_report,
)

SOFT_MATCH_THRESHOLD = 0.80


async def _run_pipelines(abstract: str, top_k: int) -> tuple[list[str], list[str]]:
    raw_pairs = await extract_keywords(abstract, top_k=top_k)
    raw_tags = [canonicalise(p) for p, _ in raw_pairs]
    try:
        normalized = await normalize_keywords([p for p, _ in raw_pairs])
        norm_tags = [canonicalise(t.canonical_label) for t in normalized]
    except Exception as exc:  # noqa: BLE001 — record but don't crash whole run.
        print(f"  LLM normalization failed: {exc!s}")
        norm_tags = []
    return raw_tags, norm_tags


def _hard_scores(pred: Sequence[str], gold: Sequence[str]) -> tuple[float, float, float]:
    pred_set = set(pred)
    gold_set = set(gold)
    if not pred_set:
        return 0.0, 0.0, 0.0
    tp = len(pred_set & gold_set)
    p = tp / len(pred_set)
    r = tp / len(gold_set) if gold_set else 0.0
    return p, r, f1(p, r)


async def _soft_scores(pred: Sequence[str], gold: Sequence[str]) -> tuple[float, float, float]:
    if not pred or not gold:
        return 0.0, 0.0, 0.0
    pred_vecs = [await embed_text(p) for p in pred]
    gold_vecs = [await embed_text(g) for g in gold]

    matched_pred, matched_gold = 0, 0
    for pv in pred_vecs:
        if any(cosine_similarity(pv, gv) >= SOFT_MATCH_THRESHOLD for gv in gold_vecs):
            matched_pred += 1
    for gv in gold_vecs:
        if any(cosine_similarity(pv, gv) >= SOFT_MATCH_THRESHOLD for pv in pred_vecs):
            matched_gold += 1

    p = matched_pred / len(pred)
    r = matched_gold / len(gold)
    return p, r, f1(p, r)


async def main_async(gold_path: Path, top_k: int) -> None:
    rows = jsonl_lines(gold_path)
    if not rows:
        raise SystemExit(f"No rows in {gold_path}")

    per_paper = []
    for i, row in enumerate(rows, 1):
        gold = [canonicalise(t) for t in row.get("gold_tags", [])]
        if not gold:
            print(f"[{i}/{len(rows)}] SKIP (no gold tags) {row.get('publication_id')}")
            continue
        print(f"[{i}/{len(rows)}] {row.get('publication_id')}")

        raw, norm = await _run_pipelines(row["abstract"], top_k)
        raw_k, norm_k = raw[:top_k], norm[:top_k]

        rh = _hard_scores(raw_k, gold)
        nh = _hard_scores(norm_k, gold)
        rs = await _soft_scores(raw_k, gold)
        ns = await _soft_scores(norm_k, gold)

        per_paper.append(
            {
                "publication_id": row.get("publication_id"),
                "gold": gold,
                "scibert_only": raw_k,
                "scibert_llm": norm_k,
                "scibert_only_hard": {"P": rh[0], "R": rh[1], "F1": rh[2]},
                "scibert_llm_hard": {"P": nh[0], "R": nh[1], "F1": nh[2]},
                "scibert_only_soft": {"P": rs[0], "R": rs[1], "F1": rs[2]},
                "scibert_llm_soft": {"P": ns[0], "R": ns[1], "F1": ns[2]},
            }
        )

    def agg(key: str, metric: str) -> float:
        return mean(p[key][metric] for p in per_paper) if per_paper else 0.0

    summary = {
        "k": top_k,
        "n_papers": len(per_paper),
        "scibert_only": {
            "hard": {m: agg("scibert_only_hard", m) for m in ("P", "R", "F1")},
            "soft": {m: agg("scibert_only_soft", m) for m in ("P", "R", "F1")},
        },
        "scibert_llm": {
            "hard": {m: agg("scibert_llm_hard", m) for m in ("P", "R", "F1")},
            "soft": {m: agg("scibert_llm_soft", m) for m in ("P", "R", "F1")},
        },
    }

    md = _format_markdown(summary)
    json_path, md_path = write_report("nlp", {"summary": summary, "per_paper": per_paper}, md)
    print(md)
    print(f"\nWrote {json_path}\nWrote {md_path}")


def _format_markdown(s: dict) -> str:
    def row(label, blk):
        return (
            f"| {label} | {blk['hard']['P']:.3f} | {blk['hard']['R']:.3f} | "
            f"{blk['hard']['F1']:.3f} | {blk['soft']['P']:.3f} | "
            f"{blk['soft']['R']:.3f} | {blk['soft']['F1']:.3f} |"
        )

    return (
        f"# NLP evaluation (n={s['n_papers']}, K={s['k']})\n\n"
        "| Pipeline | Hard P | Hard R | Hard F1 | Soft P | Soft R | Soft F1 |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{row('SciBERT only', s['scibert_only'])}\n"
        f"{row('SciBERT + LLM', s['scibert_llm'])}\n\n"
        "Acceptance: hard F1 >= 0.85 OR soft F1 >= 0.90.\n"
    )


async def _emit_pairs(out: Path) -> None:
    """Generate the raw-vs-normalized comparison table for Study 3."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.db.models import User, UserExpertiseTag, ExpertiseTag, Publication, PublicationAbstract
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        users = (
            await session.execute(
                select(User).options(selectinload(User.publications)).limit(20)
            )
        ).scalars().all()

        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "staff_id",
                    "staff_name",
                    "raw_keywords",
                    "normalized_tags",
                    "reviewer_id",
                    "accuracy",
                    "specificity",
                    "preference",
                    "comment",
                ]
            )
            for user in users:
                texts = []
                for pub in user.publications:
                    abst = await session.get(PublicationAbstract, pub.id) if False else None
                    # Re-load abstract via its own query (model uses unique FK).
                from sqlalchemy import select as _select
                abst_rows = (
                    await session.execute(
                        _select(PublicationAbstract).where(
                            PublicationAbstract.publication_id.in_(
                                [p.id for p in user.publications]
                            )
                        )
                    )
                ).scalars().all()
                texts = [a.abstract_text for a in abst_rows if a.abstract_text]
                if not texts:
                    continue
                blob = "\n\n".join(texts[:5])
                raw = await extract_keywords(blob, top_k=15)
                norm = await normalize_keywords([p for p, _ in raw])
                writer.writerow(
                    [
                        str(user.id),
                        user.full_name,
                        "; ".join(p for p, _ in raw),
                        "; ".join(t.canonical_label for t in norm),
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
        print(f"Wrote pair table to {out}. Duplicate rows for R1/R2/R3 before sending.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path("evaluation/datasets/gold_tags.jsonl"))
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--emit-pairs", type=Path, default=None)
    args = parser.parse_args()

    if args.emit_pairs:
        asyncio.run(_emit_pairs(args.emit_pairs))
    else:
        asyncio.run(main_async(args.gold, args.k))


if __name__ == "__main__":
    main()
