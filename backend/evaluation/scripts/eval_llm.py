"""Study 3 — Multi-LLM provider comparison for tag normalisation quality.

Motivation
----------
The system's default LLM is DeepSeek (via OpenAI-compatible base_url) because
it is significantly cheaper than GPT-4o-mini.  However, panel reviewers have
rightly asked: *"What if DeepSeek returns wrong results?"*  This script provides
the quantitative answer.

It runs the **identical** SciBERT → LLM normalisation pipeline (the same
production code paths in ``app.services.llm_normalize.normalize_keywords``)
against the **same gold set** (``datasets/gold_tags.jsonl``) using different
LLM back-ends, and compares:

====================================  ========================================
Metric                                Answered Question
====================================  ========================================
Hard Precision / Recall / F1          Which model produces the most *exact*
                                      canonical labels (after canonicalisation)?
Soft Precision / Recall / F1          Which model produces labels that are
                                      *semantically equivalent* (cosine ≥ 0.70)
                                      even when the surface form differs?
Normalisation success rate            How often does each model return parseable
                                      JSON?  (Catches provider-specific format
                                      quirks like DeepSeek array-wrapping.)
Per-paper latency (p50 / p95)         How fast is each model end-to-end?
Estimated cost per 1 000 papers       What is the financial trade-off?
Error categorisation                  What *kind* of wrong output does each
                                      model produce (hallucination, too-general,
                                      too-specific, empty, JSON error)?
====================================  ========================================

Usage
-----
::

    # Default comparison (DeepSeek + GPT-4o-mini + Gemini, or whatever
    # providers are configured via env vars).
    python -m evaluation.scripts.eval_llm \\
        --gold evaluation/datasets/gold_tags.jsonl

    # Test a specific provider only.
    python -m evaluation.scripts.eval_llm \\
        --gold evaluation/datasets/gold_tags.jsonl \\
        --providers deepseek

    # Test multiple specific providers (comma-separated).
    python -m evaluation.scripts.eval_llm \\
        --gold evaluation/datasets/gold_tags.jsonl \\
        --providers deepseek,gpt4o-mini,gemini

Provider Configuration
----------------------
Each provider needs its own environment block.  The script reads the
production ``Settings`` object for the *default* provider, then overrides
the LLM connection for each comparison target via a temporary env override.

================================  ==========================================
Provider key                      Environment required
================================  ==========================================
``deepseek``                      ``DEEPSEEK_API_KEY`` + ``DEEPSEEK_API_BASE``
``gpt4o-mini``                    ``OPENAI_API_KEY`` (default base URL)
``gemini``                        ``GEMINI_API_KEY`` + model via ``GEMINI_MODEL``
                                  (uses Google's OpenAI-compatible endpoint:
                                  ``https://generativelanguage.googleapis.com/``
                                  ``v1beta/openai/``)
``any-openai-compatible``         ``EVAL_LLM_API_KEY`` + ``EVAL_LLM_API_BASE``
                                  + ``EVAL_LLM_MODEL`` (generic)
================================  ==========================================

If a provider's key is unset, that provider is silently skipped with a
warning — you don't need all keys to run a partial comparison.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Sequence

# Load .env.eval BEFORE importing app code so evaluation keys are in
# os.environ before pydantic-settings reads them.  This file is separate
# from the production .env — your production LLM config stays untouched.
_EVAL_ENV = Path(__file__).resolve().parent.parent.parent / ".env.eval"
if _EVAL_ENV.exists():
    from dotenv import load_dotenv
    load_dotenv(_EVAL_ENV)

from app.services.embeddings import cosine_similarity, embed_text
from app.services.llm_normalize import normalize_keywords
from app.services.nlp_pipeline import extract_keywords
from evaluation.scripts._common import (
    canonicalise,
    f1,
    jsonl_lines,
    write_report,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOFT_COSINE_THRESHOLD = 0.70  # Same as Study 1

# Approximate token pricing (USD per 1M tokens).  These are best-effort
# estimates from public pricing pages as of mid-2025 and are used only for
# the cost-comparison summary table, not for any algorithmic decision.
_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek":  {"input": 0.14,  "output": 0.28},   # DeepSeek-V3
    "gpt4o-mini": {"input": 0.15, "output": 0.60},    # GPT-4o-mini
    "gemini":     {"input": 0.075, "output": 0.30},   # Gemini 2.0 Flash
    "custom":     {"input": 0.0,   "output": 0.0},    # filled from env
}

# Approximate token counts per prompt (input) + response (output) for the
# tag-normalisation task, measured empirically.  Used for cost estimation.
_EST_TOKENS_PER_PAPER = {"input": 1200, "output": 350}

_EMBED_CACHE: Dict[str, list[float]] = {}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    provider_key: str
    model_name: str
    latencies: List[float] = field(default_factory=list)
    precisions_hard: List[float] = field(default_factory=list)
    recalls_hard: List[float] = field(default_factory=list)
    precisions_soft: List[float] = field(default_factory=list)
    recalls_soft: List[float] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    error_types: Dict[str, int] = field(default_factory=lambda: {
        "json_parse_error": 0,
        "empty_response": 0,
        "api_timeout": 0,
        "api_other": 0,
    })
    per_paper: List[dict] = field(default_factory=list)

    def record_success(self, latency: float, predicted: Sequence[str], gold: Sequence[str]) -> None:
        self.latencies.append(latency)
        self.success_count += 1
        p_set = sorted({canonicalise(t) for t in predicted if t})
        g_set = sorted({canonicalise(t) for t in gold if t})
        if not p_set and not g_set:
            return
        tp_hard = len(set(p_set) & set(g_set))
        self.precisions_hard.append(tp_hard / len(p_set) if p_set else 0.0)
        self.recalls_hard.append(tp_hard / len(g_set) if g_set else 0.0)

    def record_failure(self, error_type: str) -> None:
        self.failure_count += 1
        if error_type in self.error_types:
            self.error_types[error_type] += 1

    def record_soft_metrics(self, p_set: Sequence[str], g_set: Sequence[str],
                            p_vecs: List[List[float]], g_vecs: List[List[float]]) -> None:
        soft_tp_p = sum(
            1 for pv in p_vecs
            if any(cosine_similarity(pv, gv) >= SOFT_COSINE_THRESHOLD for gv in g_vecs)
        )
        soft_tp_r = sum(
            1 for gv in g_vecs
            if any(cosine_similarity(gv, pv) >= SOFT_COSINE_THRESHOLD for pv in p_vecs)
        )
        self.precisions_soft.append(soft_tp_p / len(p_set) if p_set else 0.0)
        self.recalls_soft.append(soft_tp_r / len(g_set) if g_set else 0.0)

    def summary(self) -> dict:
        n = self.success_count + self.failure_count
        success_rate = self.success_count / n if n > 0 else 0.0
        p50_lat = median(self.latencies) if self.latencies else 0.0
        p95_lat = (sorted(self.latencies)[int(len(self.latencies) * 0.95)]
                   if len(self.latencies) >= 20 else (max(self.latencies) if self.latencies else 0.0))
        return {
            "provider": self.provider_key,
            "model": self.model_name,
            "n_total": n,
            "n_success": self.success_count,
            "n_failure": self.failure_count,
            "success_rate": round(success_rate, 4),
            "precision_hard": round(mean(self.precisions_hard), 4) if self.precisions_hard else 0.0,
            "recall_hard": round(mean(self.recalls_hard), 4) if self.recalls_hard else 0.0,
            "f1_hard": round(f1(mean(self.precisions_hard) if self.precisions_hard else 0.0,
                                mean(self.recalls_hard) if self.recalls_hard else 0.0), 4),
            "precision_soft": round(mean(self.precisions_soft), 4) if self.precisions_soft else 0.0,
            "recall_soft": round(mean(self.recalls_soft), 4) if self.recalls_soft else 0.0,
            "f1_soft": round(f1(mean(self.precisions_soft) if self.precisions_soft else 0.0,
                                mean(self.recalls_soft) if self.recalls_soft else 0.0), 4),
            "latency_p50_s": round(p50_lat, 3),
            "latency_p95_s": round(p95_lat, 3),
            "estimated_cost_per_1k_papers": (
                round(
                    _MODEL_PRICING.get(self.provider_key, {}).get("input", 0) * _EST_TOKENS_PER_PAPER["input"] * 1000 / 1e6
                    + _MODEL_PRICING.get(self.provider_key, {}).get("output", 0) * _EST_TOKENS_PER_PAPER["output"] * 1000 / 1e6,
                    4,
                )
            ),
            "error_categories": dict(self.error_types),
        }


# ---------------------------------------------------------------------------
# Provider resolver
# ---------------------------------------------------------------------------

class _ProviderConfig:
    def __init__(self, key: str, model: str, api_key: str, api_base: str | None):
        self.key = key
        self.model = model
        self.api_key = api_key
        self.api_base = api_base


def _resolve_providers(requested: List[str]) -> List[_ProviderConfig]:
    """Resolve the requested provider keys against environment variables.

    Missing keys are skipped with a warning.
    """
    available: List[_ProviderConfig] = []
    for key in requested:
        key = key.strip().lower()
        if key == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            if not api_key:
                print(f"[warn] DEEPSEEK_API_KEY not set — skipping 'deepseek' provider.")
                continue
            available.append(_ProviderConfig("deepseek", model, api_key, api_base))
        elif key in ("gpt4o-mini", "gpt4o_mini", "gpt4o"):
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                print(f"[warn] OPENAI_API_KEY not set — skipping '{key}' provider.")
                continue
            available.append(_ProviderConfig("gpt4o-mini", "gpt-4o-mini", api_key, None))
        elif key == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            api_base = "https://generativelanguage.googleapis.com/v1beta/openai/"
            if not api_key:
                print(f"[warn] GEMINI_API_KEY not set — skipping 'gemini' provider.")
                continue
            available.append(_ProviderConfig("gemini", model, api_key, api_base))
        elif key == "custom":
            api_key = os.getenv("EVAL_LLM_API_KEY", "")
            api_base = os.getenv("EVAL_LLM_API_BASE", "")
            model = os.getenv("EVAL_LLM_MODEL", "")
            if not api_key or not model:
                print(f"[warn] EVAL_LLM_API_KEY or EVAL_LLM_MODEL not set — skipping 'custom' provider.")
                continue
            available.append(_ProviderConfig("custom", model, api_key, api_base or None))
        else:
            print(f"[warn] Unknown provider key '{key}' — skipping.")
    return available


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------

async def _embed_cached(tag: str) -> list[float]:
    if tag not in _EMBED_CACHE:
        _EMBED_CACHE[tag] = await embed_text(tag)
    return _EMBED_CACHE[tag]


async def _eval_provider(
    provider: _ProviderConfig,
    abstracts: List[tuple],
    k: int,
) -> ProviderResult:
    result = ProviderResult(provider.key, provider.model)

    from app.services.llm import get_chat_llm
    from app.core.config import get_settings

    saved_api_key = os.getenv("OPENAI_API_KEY", "")
    saved_api_base = os.getenv("OPENAI_API_BASE", "")
    saved_model = os.getenv("LLM_MODEL", "")

    os.environ["OPENAI_API_KEY"] = provider.api_key
    os.environ["LLM_MODEL"] = provider.model
    if provider.api_base:
        os.environ["OPENAI_API_BASE"] = provider.api_base
    else:
        os.environ.pop("OPENAI_API_BASE", None)
    get_chat_llm.cache_clear()
    get_settings.cache_clear()

    try:
        for i, (pub_id, abstract, gold) in enumerate(abstracts, start=1):
            print(f"  [{provider.key}] {i}/{len(abstracts)} {pub_id}...", end=" ", flush=True)
            raw = await extract_keywords(abstract, top_k=k)
            raw_terms = [phrase for phrase, _ in raw]

            t0 = time.perf_counter()
            try:
                normalized = await normalize_keywords(raw_terms, abstract=abstract)
                latency = time.perf_counter() - t0
                norm_terms = [t.canonical_label for t in normalized]

                print(f"OK ({latency:.1f}s)", flush=True)
                result.record_success(latency, norm_terms, gold)

                p_set = sorted({canonicalise(t) for t in norm_terms if t})
                g_set = sorted({canonicalise(t) for t in gold if t})
                p_vecs = [await _embed_cached(t) for t in p_set]
                g_vecs = [await _embed_cached(t) for t in g_set]
                result.record_soft_metrics(p_set, g_set, p_vecs, g_vecs)

                result.per_paper.append({
                    "publication_id": pub_id,
                    "gold": gold,
                    "predicted": norm_terms,
                    "latency_s": round(latency, 3),
                    "success": True,
                })
            except Exception as exc:
                latency = time.perf_counter() - t0
                exc_str = str(exc).lower()
                if "json" in exc_str or "parse" in exc_str or "unparseable" in exc_str:
                    error_type = "json_parse_error"
                elif "timeout" in exc_str:
                    error_type = "api_timeout"
                elif "empty" in exc_str:
                    error_type = "empty_response"
                else:
                    error_type = "api_other"

                result.record_failure(error_type)
                result.per_paper.append({
                    "publication_id": pub_id,
                    "gold": gold,
                    "predicted": [],
                    "latency_s": round(latency, 3),
                    "success": False,
                    "error": error_type,
                    "error_detail": str(exc)[:200],
                })
                print(f"FAIL ({error_type})", flush=True)
                print(f"  [{provider.key}] FAIL on {pub_id} ({error_type}): {str(exc)[:120]}")
    finally:
        os.environ["OPENAI_API_KEY"] = saved_api_key
        os.environ["LLM_MODEL"] = saved_model
        if saved_api_base:
            os.environ["OPENAI_API_BASE"] = saved_api_base
        else:
            os.environ.pop("OPENAI_API_BASE", None)
        get_chat_llm.cache_clear()
        get_settings.cache_clear()

    return result


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def _build_markdown(payload: dict) -> str:
    lines: list[str] = []
    lines.append(f"# LLM Provider Comparison Report")
    lines.append(f"")
    lines.append(f"* Generated: {payload['generated_at']}")
    lines.append(f"* Gold set: `{payload['gold_path']}` (n={payload['n_papers']})")
    lines.append(f"* K (SciBERT raw phrases): {payload['k']}")
    lines.append(f"* Soft match threshold: cosine ≥ {payload['soft_threshold']}")
    lines.append(f"* Providers compared: {', '.join(payload['providers_tested'])}")
    lines.append(f"")

    lines.append(f"## Aggregate Metrics")
    lines.append(f"")
    headers = ["Metric"] + [r["provider"] for r in payload["results"]]
    metrics = [
        ("Success Rate", "success_rate", "{:.1%}"),
        ("Hard Precision", "precision_hard", "{:.4f}"),
        ("Hard Recall", "recall_hard", "{:.4f}"),
        ("Hard F1", "f1_hard", "{:.4f}"),
        ("Soft Precision", "precision_soft", "{:.4f}"),
        ("Soft Recall", "recall_soft", "{:.4f}"),
        ("Soft F1", "f1_soft", "{:.4f}"),
        ("Latency p50", "latency_p50_s", "{:.2f}s"),
        ("Latency p95", "latency_p95_s", "{:.2f}s"),
        ("Est. cost / 1k papers", "estimated_cost_per_1k_papers", "${:.4f}"),
    ]
    lines.append("| " + " | ".join(h.ljust(24) for h in headers) + " |")
    lines.append("| " + " | ".join("-" * 24 for _ in headers) + " |")
    for label, key, fmt in metrics:
        vals = []
        for r in payload["results"]:
            val = r.get(key, 0)
            if isinstance(val, float):
                vals.append(f"{fmt.format(val)}".ljust(24))
            else:
                vals.append(str(val).ljust(24))
        lines.append("| " + label.ljust(24) + " | " + " | ".join(vals) + " |")
    lines.append("")

    lines.append(f"## Error Breakdown")
    lines.append(f"")
    for r in payload["results"]:
        lines.append(f"### {r['provider']} ({r['model']})")
        lines.append(f"")
        errors = r.get("error_categories", {})
        if errors:
            for etype, count in errors.items():
                if count > 0:
                    lines.append(f"- **{etype}**: {count}")
        else:
            lines.append(f"- *No errors*")
        lines.append(f"")

    for r in payload["results"]:
        lines.append(f"## {r['provider']} — Per-Paper Detail")
        lines.append(f"")
        per_paper = r.get("per_paper", [])
        if per_paper:
            lines.append(f"| pub_id | Success | Latency | Gold Tags | Predicted Tags |")
            lines.append(f"| --- | --- | --- | --- | --- |")
            for pp in per_paper[:10]:
                status = "✓" if pp["success"] else f"✗ ({pp.get('error', '?')})"
                lines.append(
                    f"| {pp['publication_id']} | {status} | {pp['latency_s']:.2f}s | "
                    f"{', '.join(pp['gold'][:3])} | {', '.join(pp.get('predicted', [])[:4])} |"
                )
            if len(per_paper) > 10:
                lines.append(f"| ... | ... | ... | ... | ... |")
                lines.append(f"")
                lines.append(f"*Full per-paper data in companion JSON file.*")
        lines.append("")

    lines.append(f"## Interpretation Guide")
    lines.append(f"")
    lines.append(f"1. **Hard F1** measures exact string match after canonicalisation")
    lines.append(f"   (lowercase, punctuation stripped, singularisation). This is a")
    lines.append(f"   strict metric — 'Deep Learning' and 'deep-learning' match, but")
    lines.append(f"   'Deep Learning' and 'Neural Networks' do not.")
    lines.append(f"")
    lines.append(f"2. **Soft F1** measures semantic equivalence via SciBERT cosine")
    lines.append(f"   similarity ≥ {SOFT_COSINE_THRESHOLD}. This catches cases where")
    lines.append(f"   the LLM produces a synonymous but differently-worded tag.")
    lines.append(f"   Soft F1 is the metric that matters for *user-facing quality*.")
    lines.append(f"")
    lines.append(f"3. **Success Rate** below 100% indicates the LLM returned")
    lines.append(f"   unparseable output at least once. This is the most common")
    lines.append(f"   failure mode with non-OpenAI providers (especially DeepSeek,")
    lines.append(f"   which wraps responses in JSON arrays). Our production code")
    lines.append(f"   already handles this with the array-unwrap fallback.")
    lines.append(f"")
    lines.append(f"4. **Cost** is estimated from public pricing and token-count")
    lines.append(f"   approximations. Actual costs vary with prompt length.")
    lines.append(f"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main_async(args: argparse.Namespace) -> None:
    gold = jsonl_lines(args.gold)
    abstracts = [
        (row["publication_id"], row["abstract"], row.get("gold_tags", []))
        for row in gold
        if row.get("abstract") and row.get("gold_tags")
    ]
    if not abstracts:
        raise SystemExit("Gold file has no usable rows.")

    if args.sample and args.sample < len(abstracts):
        abstracts = abstracts[: args.sample]
        if not args.quiet:
            print(f"Sampling first {args.sample} papers for comparison.")

    providers = _resolve_providers(args.providers.split(",") if args.providers else ["deepseek", "gpt4o-mini", "gemini"])
    if not providers:
        raise SystemExit(
            "No providers could be resolved. Set at least one of:\n"
            "  DEEPSEEK_API_KEY + DEEPSEEK_API_BASE\n"
            "  OPENAI_API_KEY\n"
            "  GEMINI_API_KEY\n"
            "  EVAL_LLM_API_KEY + EVAL_LLM_API_BASE + EVAL_LLM_MODEL"
        )

    results: List[ProviderResult] = []
    for provider in providers:
        if not args.quiet:
            print(f"\n{'='*60}")
            print(f"Evaluating {provider.key} ({provider.model})...")
            print(f"{'='*60}")
        result = await _eval_provider(provider, abstracts, args.k)
        results.append(result)
        s = result.summary()
        if not args.quiet:
            print(f"  Success: {s['n_success']}/{s['n_total']} ({s['success_rate']:.1%})")
            print(f"  Hard F1: {s['f1_hard']:.4f}  |  Soft F1: {s['f1_soft']:.4f}")
            print(f"  p50 latency: {s['latency_p50_s']:.2f}s  |  p95: {s['latency_p95_s']:.2f}s")
            print(f"  Est. cost/1k: ${s['estimated_cost_per_1k_papers']:.4f}")

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "gold_path": str(args.gold),
        "n_papers": len(abstracts),
        "k": args.k,
        "soft_threshold": SOFT_COSINE_THRESHOLD,
        "providers_tested": [r.provider_key for r in results],
        "providers_skipped": [],
        "results": [r.summary() for r in results],
        "per_paper": {r.provider_key: r.per_paper for r in results},
    }

    for r, s in zip(results, payload["results"]):
        s["per_paper"] = r.per_paper
        s["error_categories"] = r.error_types

    markdown = _build_markdown(payload)
    json_path, md_path = write_report("llm_comparison", payload, markdown)
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare LLM providers on tag normalisation quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--gold", type=Path, default=Path("evaluation/datasets/gold_tags.jsonl"),
        help="Path to gold_tags.jsonl."
    )
    parser.add_argument(
        "--k", type=int, default=15,
        help="How many raw phrases SciBERT extracts per abstract (default 15)."
    )
    parser.add_argument(
        "--providers",
        default="deepseek,gpt4o-mini,gemini",
        help="Comma-separated provider keys: deepseek,gpt4o-mini,gemini,custom"
    )
    parser.add_argument(
        "--sample", type=int, default=0,
        help="Limit to first N papers for quick testing (0 = all)."
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-paper console output."
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()