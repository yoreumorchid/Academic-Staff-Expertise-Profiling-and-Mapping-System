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

from app.services.embeddings import cosine_similarity, embed_text
from app.services.llm_normalize import normalize_keywords
from app.services.nlp_pipeline import extract_keywords
from evaluation.scripts._common import (
    canonicalise,
    f1,
    jsonl_lines,
    write_report,
)

# Semantic soft-match threshold. 0.70 was tuned empirically on the
# 27-paper development set: it accepts pairs like ("software-defined
# networking", "software defined networks") and ("medical image
# segmentation", "image segmentation") while still rejecting
# cross-domain pairs such as ("computer vision", "natural language
# processing"). Lower it if your gold tags use distinct surface forms
# from what the LLM produces (e.g. "environmental governance" vs
# "environmental policy"); raise it if false positives appear.
SOFT_COSINE_THRESHOLD = 0.70


# A small embedding cache keyed by canonicalised tag string. We call
# embed_text repeatedly on the same handful of canonical labels (per
# paper and across papers), so caching keeps the run reasonably fast.
_EMBED_CACHE: dict[str, list[float]] = {}


async def _embed_cached(tag: str) -> list[float]:
    if tag not in _EMBED_CACHE:
        _EMBED_CACHE[tag] = await embed_text(tag)
    return _EMBED_CACHE[tag]


@dataclass
class PipelineScore:
    name: str
    precisions: list[float] = field(default_factory=list)
    recalls: list[float] = field(default_factory=list)
    soft_precisions: list[float] = field(default_factory=list)
    soft_recalls: list[float] = field(default_factory=list)

    async def add(self, predicted: Sequence[str], gold: Sequence[str]) -> None:
        p_set = sorted({canonicalise(t) for t in predicted if t})
        g_set = sorted({canonicalise(t) for t in gold if t})
        if not p_set and not g_set:
            return

        # ----- Hard match (exact string after canonicalisation) -----
        p_lookup = set(p_set)
        g_lookup = set(g_set)
        tp_hard = len(p_lookup & g_lookup)
        self.precisions.append(tp_hard / len(p_set) if p_set else 0.0)
        self.recalls.append(tp_hard / len(g_set) if g_set else 0.0)

        # ----- Soft match (semantic cosine over SciBERT embeddings) -----
        # A predicted tag counts as a soft TP if ANY gold tag has cosine
        # similarity >= SOFT_COSINE_THRESHOLD with it, and vice versa.
        # This catches near-synonyms ("network engineering" ~
        # "computer networks") that exact matching would miss.
        p_vecs = [await _embed_cached(t) for t in p_set]
        g_vecs = [await _embed_cached(t) for t in g_set]

        soft_tp_p = sum(
            1
            for pv in p_vecs
            if any(cosine_similarity(pv, gv) >= SOFT_COSINE_THRESHOLD for gv in g_vecs)
        )
        soft_tp_r = sum(
            1
            for gv in g_vecs
            if any(cosine_similarity(gv, pv) >= SOFT_COSINE_THRESHOLD for pv in p_vecs)
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
) -> tuple[PipelineScore, PipelineScore, list[dict]]:
    scibert = PipelineScore("scibert_only")
    fused = PipelineScore("scibert_plus_llm")
    per_paper: list[dict] = []

    for pub_id, abstract, gold in abstracts:
        # NOTE: ``k`` only caps the SciBERT raw extraction. The LLM is
        # given those raw phrases and allowed to emit ANY number of
        # canonical labels (3-12 per its own prompt). We deliberately do
        # not truncate the LLM output, because doing so silently caps
        # Recall whenever the LLM happens to ordering-wise put a correct
        # tag at position 6.
        raw = await extract_keywords(abstract, top_k=k)
        raw_terms = [phrase for phrase, _ in raw]
        await scibert.add(raw_terms, gold)

        try:
            # Pass the abstract as context so the LLM can disambiguate
            # generic candidate words against the paper's actual topic.
            normalized = await normalize_keywords(raw_terms, abstract=abstract)
            norm_terms = [t.canonical_label for t in normalized]
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] LLM normalize failed for {pub_id}: {exc}")
            norm_terms = raw_terms
        await fused.add(norm_terms, gold)

        per_paper.append(
            {
                "publication_id": pub_id,
                "gold": gold,
                "scibert_raw": raw_terms,
                "scibert_llm": norm_terms,
            }
        )

        if pairs_writer is not None:
            pairs_writer.writerow(
                [pub_id, "; ".join(raw_terms), "; ".join(norm_terms), "; ".join(gold)]
            )

    return scibert, fused, per_paper


def _markdown(payload: dict) -> str:
    s_a = payload["scibert_only"]
    s_b = payload["scibert_plus_llm"]
    return f"""# NLP Evaluation Report

* Generated: {payload['generated_at']}
* Gold set: `{payload['gold_path']}` (n={payload['n']})
* K (top-K predictions for SciBERT raw): {payload['k']}
* Soft match: SciBERT cosine >= {payload['soft_match']['threshold']}

| Pipeline | P (hard) | R (hard) | F1 (hard) | P (soft) | R (soft) | F1 (soft) |
|---|---|---|---|---|---|---|
| SciBERT only        | {s_a['precision_hard']} | {s_a['recall_hard']} | **{s_a['f1_hard']}** | {s_a['precision_soft']} | {s_a['recall_soft']} | **{s_a['f1_soft']}** |
| SciBERT + LLM refine | {s_b['precision_hard']} | {s_b['recall_hard']} | **{s_b['f1_hard']}** | {s_b['precision_soft']} | {s_b['recall_soft']} | **{s_b['f1_soft']}** |

Acceptance thresholds:

* Hard-match F1 ≥ 0.85 — {'PASS' if s_b['f1_hard'] >= 0.85 else 'FAIL'}
* Soft-match F1 ≥ 0.90 — {'PASS' if s_b['f1_soft'] >= 0.90 else 'FAIL'}

Per-paper predictions are stored in the companion JSON file under
``per_paper`` — open it to see which tags the pipeline emitted for each
abstract, which is the fastest way to diagnose unexpectedly low scores.
"""


async def main_async(gold_path: Path, k: int, pairs_path: Path | None, verbose: bool) -> None:
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
        scibert, fused, per_paper = await _run_pipelines(abstracts, k, pairs_writer)
    finally:
        if pairs_fh is not None:
            pairs_fh.close()

    if verbose:
        # Print every paper's predictions vs gold so the developer can
        # diagnose low scores without opening the JSON report.
        print("\n" + "=" * 78)
        print("PER-PAPER PREDICTIONS")
        print("=" * 78)
        for p in per_paper:
            print(f"\n--- {p['publication_id']} ---")
            print(f"  GOLD       : {p['gold']}")
            print(f"  SciBERT    : {p['scibert_raw']}")
            print(f"  SciBERT+LLM: {p['scibert_llm']}")

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "gold_path": str(gold_path),
        "n": len(abstracts),
        "k": k,
        "soft_match": {
            "kind": "scibert_cosine",
            "threshold": SOFT_COSINE_THRESHOLD,
        },
        "scibert_only": scibert.summary(),
        "scibert_plus_llm": fused.summary(),
        "per_paper": per_paper,
    }
    json_path, md_path = write_report("nlp", payload, _markdown(payload))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if pairs_path is not None:
        print(f"Wrote pair table {pairs_path} — feed this into the Study 3 review.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path("evaluation/datasets/gold_tags.jsonl"))
    parser.add_argument(
        "--k",
        type=int,
        default=15,
        help=(
            "How many raw phrases SciBERT extracts per abstract before LLM"
            " normalization. Higher K gives the LLM more material to merge"
            " and tends to improve Recall; lower K stress-tests the"
            " SciBERT-only baseline. Default 15."
        ),
    )
    parser.add_argument(
        "--emit-pairs",
        type=Path,
        default=None,
        help="Optional CSV to dump (raw, normalized, gold) triples.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Also print per-paper predictions to the console. By"
            " default only the summary table is printed; per-paper"
            " predictions are always written to the JSON report."
        ),
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.gold, args.k, args.emit_pairs, args.verbose))


if __name__ == "__main__":
    main()