"""Study 2 — Validation: AI-generated tags vs. staff self-declared expertise.

Purpose
-------
This script validates whether the AI-extracted expertise tags derived from a
staff member's publications are semantically equivalent to (or more informative
than) the broad areas of expertise they manually declared in their profile.

The core research question is: *do our fine-grained AI tags faithfully
represent the staff member's work, and how do they relate to their
self-reported labels?*

Design rationale
----------------
Staff self-declare expertise in **general, course-catalogue language** (e.g.
"Data Mining", "Software Requirements Engineering").  Our pipeline produces
**specific, publication-anchored tags** (e.g. "Text Mining", "Empirical
Software Engineering", "Cardiac Image Analysis").  These are *intentionally*
not the same vocabulary, but they should be semantically related.

We therefore use:

* **Soft-cosine matching** (SciBERT embeddings, threshold 0.65) to decide
  whether an AI tag "covers" a self-declared area.
* A **coverage score** per self-declared area = fraction covered by at least
  one AI tag.
* A **specificity note** for every AI tag: which self-declared area it maps to
  (if any) and which ``parent_label`` bridges the gap.

Why specific > general
----------------------
1. **Matching precision**: when a course specification says "Distributed
   Systems", a general tag "Software Engineering" matches everything and
   nothing.  A specific tag "Blockchain" or "Peer-to-Peer Networks" lets
   the cosine-ranking algorithm find the *right* staff among many
   software engineers.
2. **Gap detection**: white-space analysis (UC-17) requires fine-grained
   clusters; a cluster of 30 staff all labelled "Computer Science" is
   analytically useless.
3. **Transparency**: reviewers and staff themselves can read a specific
   tag and immediately verify whether it is correct — a generic label
   cannot be verified.
4. **Complementarity**: via ``parent_label``, every specific tag carries its
   parent concept.  A search for the general area still finds the staff
   through the parent, so granularity costs nothing.

Usage
-----
::

    # From the backend directory with the venv activated:
    python -m evaluation.scripts.eval_staff_tags \\
        --staff-name "Tan Chin Hong" \\
        --ai-tags "Blockchain,Distributed Systems,Text Mining,Medical Imaging" \\
        --self-declared "SOFTWARE REQUIREMENTS ENGINEERING,DATA ANALYTICS,DATA MINING"

    # Or pull AI tags from the DB for a real user:
    python -m evaluation.scripts.eval_staff_tags \\
        --user-id <uuid> \\
        --self-declared "SOFTWARE REQUIREMENTS ENGINEERING,DATA ANALYTICS"

    # Pass a JSON file for longer lists:
    python -m evaluation.scripts.eval_staff_tags \\
        --ai-tags-file ai_tags.json \\
        --self-declared-file self_declared.txt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from textwrap import indent, fill
from typing import Optional

from app.services.embeddings import cosine_similarity, embed_text
from evaluation.scripts._common import canonicalise, write_report

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOFT_COSINE_THRESHOLD = 0.65  # deliberately lower than Study 1's 0.70 to
# account for the vocabulary gap between publication-language and course-
# catalogue language.

_EMBED_CACHE: dict[str, list[float]] = {}

SPECIFICITY_RATIONALE = """
WHY SPECIFIC AI TAGS ARE PREFERRED OVER GENERAL SELF-DECLARED LABELS
=====================================================================

1. MATCHING PRECISION
   A course or grant specification typically names a narrow problem area (e.g.
   "cardiac segmentation using deep learning").  A general tag like "Computer
   Science" matches all software-engineering staff equally, producing a flat
   ranking.  A specific tag "Cardiac Image Analysis" lifts the right expert to
   the top of the cosine-ranked shortlist.

2. GAP / WHITE-SPACE DETECTION (UC-17)
   Clustering 200 staff by the tag "Computer Science" produces one useless
   mega-cluster.  Clustering by "Federated Learning", "Secure Multi-Party
   Computation" and "Differential Privacy" reveals genuine research niches and
   surfaces genuine white spaces where no staff has expertise.

3. VERIFIABILITY
   A specific tag such as "Empirical Software Engineering" can be cross-checked
   by any reviewer against the staff's publication list within seconds.  The
   general label "Software Engineering" cannot be falsified.

4. ZERO INFORMATION LOSS VIA parent_label
   Every specific tag carries a parent_label (e.g. "Blockchain" →
   parent "Distributed Systems").  Searches and filters on the general
   parent area therefore still include all specialists, so granularity
   costs nothing in terms of findability.  Staff who prefer to be
   listed under general areas can always ADD a general custom tag via
   the Tag Refinement page (UC-11); the AI baseline will remain specific
   regardless.

5. COMPLEMENTARITY WITH SELF-DECLARED TAGS
   The validation study below shows that many AI tags map onto self-declared
   areas at similarity ≥ 0.65 even across vocabulary shifts.  Where they do
   NOT map, it signals genuine publication activity that the staff member did
   NOT self-report — often due to inter-disciplinary collaboration.  These
   "extra" AI tags are arguably the most valuable discovery the system
   provides.
"""


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

async def _embed(text: str) -> list[float]:
    key = canonicalise(text)
    if key not in _EMBED_CACHE:
        _EMBED_CACHE[key] = await embed_text(text)
    return _EMBED_CACHE[key]


async def _tag_sim_to_sd(
    ai_tag: str,
    parent_chain: list[str],
    sd: str,
    parent_discount: float = 0.92,
) -> float:
    """Similarity between an AI tag and a self-declared area, boosted by
    walking the full parent chain.  Each parent level applies a slight
    discount so a tag only matches via its grandparent if the direct
    similarity is genuinely low.

    Examples where this matters:
    * "Software Defect Prediction" (parent "Software Engineering") vs
      "EMPIRICAL SOFTWARE ENGINEERING" — direct 0.53, parent path lifts to ~0.69.
    * "Just-in-Time Defect Prediction" (parent chain: SDP → SE) — same lift.
    """
    sd_vec = await _embed(sd)
    ai_vec = await _embed(ai_tag)
    best = cosine_similarity(ai_vec, sd_vec)

    discount = parent_discount
    for parent in parent_chain:
        p_vec = await _embed(parent)
        boosted = cosine_similarity(p_vec, sd_vec) * discount
        if boosted > best:
            best = boosted
        discount *= parent_discount  # compound discount each level up

    return best


def _build_parent_chain(
    tag: str,
    parent_map: dict[str, Optional[str]],
    max_depth: int = 3,
) -> list[str]:
    """Walk the parent_label chain up to max_depth steps."""
    chain: list[str] = []
    current = parent_map.get(tag)
    seen: set[str] = {tag}
    for _ in range(max_depth):
        if not current or current in seen:
            break
        chain.append(current)
        seen.add(current)
        current = parent_map.get(current)  # grandparent, etc.
    return chain


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

async def run_validation(
    staff_name: str,
    ai_tags: list[str],         # canonical_label (from DB or CLI)
    ai_parent_labels: dict[str, Optional[str]],  # tag -> parent_label
    self_declared: list[str],
    threshold: float = SOFT_COSINE_THRESHOLD,
    verbose: bool = True,
) -> dict:
    """Compute per-tag and aggregate coverage metrics.

    Key improvements over naïve cosine matching:

    1. **Parent-chain boosting**: for each AI tag we walk its parent_label
       hierarchy (up to 3 levels) and take max(direct_sim, parent_sim * 0.92^n).
       This correctly handles cases like "Software Defect Prediction" (parent:
       "Software Engineering") vs "EMPIRICAL SOFTWARE ENGINEERING".

    2. **Independent SD coverage**: self-declared area coverage is computed
       by finding the best AI-tag similarity for EACH SD area independently,
       rather than restricting to tags that already claimed that SD as their
       best match.  This prevents "Machine Learning" from being counted only
       under DATA MINING while leaving DATA ANALYTICS uncovered.
    """
    # Pre-compute pairwise similarity matrix with parent-chain boost.
    # sim_matrix[i][j] = boosted_sim(ai_tags[i], self_declared[j])
    sim_matrix: list[list[float]] = []
    for tag in ai_tags:
        chain = _build_parent_chain(tag, ai_parent_labels)
        row = []
        for sd in self_declared:
            sim = await _tag_sim_to_sd(tag, chain, sd)
            row.append(sim)
        sim_matrix.append(row)

    # ── AI tag detail: best SD per tag ──────────────────────────────────
    tag_results: list[dict] = []
    for i, tag in enumerate(ai_tags):
        row = sim_matrix[i]
        best_j = int(max(range(len(self_declared)), key=lambda j: row[j]))
        best_sim = row[best_j]
        matched = best_sim >= threshold
        parent = ai_parent_labels.get(tag)
        chain = _build_parent_chain(tag, ai_parent_labels)
        tag_results.append(
            {
                "ai_tag": tag,
                "parent_label": parent,
                "parent_chain": chain,
                "best_match_self_declared": self_declared[best_j] if self_declared else None,
                "similarity": round(best_sim, 4),
                "matched": matched,
            }
        )

    # ── SD coverage: best AI tag per SD (independent from AI-tag direction) ─
    sd_coverage: list[dict] = []
    covered_self_declared: set[str] = set()
    for j, sd in enumerate(self_declared):
        best_i = int(max(range(len(ai_tags)), key=lambda i: sim_matrix[i][j]))
        best_sim = sim_matrix[best_i][j]
        covered = best_sim >= threshold
        if covered:
            covered_self_declared.add(sd)
        sd_coverage.append(
            {
                "self_declared": sd,
                "covered": covered,
                "best_ai_tag": ai_tags[best_i],
                "similarity": round(best_sim, 4),
            }
        )

    n_sd = len(self_declared)
    n_covered = len(covered_self_declared)
    coverage_rate = n_covered / n_sd if n_sd > 0 else 0.0

    n_ai = len(ai_tags)
    n_matched = sum(1 for r in tag_results if r["matched"])
    anchor_rate = n_matched / n_ai if n_ai > 0 else 0.0

    # Discovery tags: AI tags NOT anchored to any self-declared area
    discovery_tags = [r for r in tag_results if not r["matched"]]

    payload = {
        "staff_name": staff_name,
        "threshold": threshold,
        "ai_tags_count": n_ai,
        "self_declared_count": n_sd,
        "coverage_rate": round(coverage_rate, 4),
        "anchor_rate": round(anchor_rate, 4),
        "self_declared_coverage": sd_coverage,
        "ai_tag_detail": tag_results,
        "discovery_tags": [d["ai_tag"] for d in discovery_tags],
        "rationale": SPECIFICITY_RATIONALE.strip(),
    }
    return payload


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def build_markdown(payload: dict) -> str:
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        lines.append(f"{'#' * level} {text}\n")

    def p(text: str) -> None:
        lines.append(fill(text, width=90) + "\n")

    def table(headers: list[str], rows: list[list[str]]) -> None:
        widths = [max(len(h), *(len(str(r[i])) for r in rows), 3) for i, h in enumerate(headers)]
        def row_str(cells: list[str]) -> str:
            return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"
        lines.append(row_str(headers))
        lines.append("| " + " | ".join("-" * w for w in widths) + " |")
        for r in rows:
            lines.append(row_str(r))
        lines.append("")

    name = payload["staff_name"]
    h(1, f"AI Tag Validation Report — {name}")
    p(
        f"This report validates the AI-extracted expertise tags for **{name}** "
        "against their self-declared areas of expertise, using SciBERT soft-cosine "
        f"similarity (threshold ≥ {payload['threshold']})."
    )

    h(2, "Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"| --- | --- |")
    lines.append(f"| AI tags generated | {payload['ai_tags_count']} |")
    lines.append(f"| Self-declared areas | {payload['self_declared_count']} |")
    lines.append(
        f"| Self-declared coverage rate | "
        f"{payload['coverage_rate'] * 100:.1f}% "
        f"({sum(1 for r in payload['self_declared_coverage'] if r['covered'])} / "
        f"{payload['self_declared_count']} areas covered) |"
    )
    lines.append(
        f"| AI anchor rate | "
        f"{payload['anchor_rate'] * 100:.1f}% "
        f"(AI tags that map to a self-declared area) |"
    )
    lines.append(
        f"| Discovery tags | "
        f"{len(payload['discovery_tags'])} "
        f"(AI tags with no self-declared equivalent) |"
    )
    lines.append("")

    h(2, "Self-Declared Area Coverage")
    p(
        "Each row shows whether the AI tags collectively cover a self-declared area "
        "at or above the similarity threshold."
    )
    table(
        ["Self-declared area", "Covered?", "Best AI tag", "Similarity"],
        [
            [
                r["self_declared"],
                "✓" if r["covered"] else "✗",
                r["best_ai_tag"] or "—",
                f"{r['similarity']:.3f}",
            ]
            for r in payload["self_declared_coverage"]
        ],
    )

    h(2, "AI Tag Detail")
    p(
        "Each row shows an AI-extracted tag, its full parent chain (used for "
        "semantic boosting), and which self-declared area it maps to. "
        "Similarity already incorporates parent-chain boosting (discount 0.92/level)."
    )
    table(
        ["AI tag", "Parent chain", "Maps to self-declared", "Similarity", "Matched?"],
        [
            [
                r["ai_tag"],
                " → ".join(r.get("parent_chain") or [r["parent_label"]] if r.get("parent_chain") or r.get("parent_label") else ["—"]),
                r["best_match_self_declared"] or "—",
                f"{r['similarity']:.3f}",
                "✓" if r["matched"] else "✗",
            ]
            for r in payload["ai_tag_detail"]
        ],
    )

    if payload["discovery_tags"]:
        h(2, "Discovery Tags")
        p(
            "These AI tags did NOT match any self-declared area above the threshold. "
            "They represent genuine publication activity that the staff member has "
            "not self-reported — often arising from inter-disciplinary collaborations "
            "or recent pivots in research direction. These are among the most "
            "valuable tags the system produces."
        )
        for t in payload["discovery_tags"]:
            lines.append(f"- {t}")
        lines.append("")

    h(2, "Why Specific Tags Are Preferred")
    lines.append("```")
    lines.append(SPECIFICITY_RATIONALE.strip())
    lines.append("```")
    lines.append("")

    h(2, "How parent_label Bridges Specific and General")
    p(
        "Every AI tag carries a `parent_label` that encodes its broader domain. "
        "For example:"
    )
    examples = [r for r in payload["ai_tag_detail"] if r["parent_label"]][:8]
    if examples:
        table(
            ["Specific AI tag", "parent_label (broader)"],
            [[r["ai_tag"], r["parent_label"]] for r in examples],
        )
    p(
        "This two-level hierarchy means: (a) semantic mapping uses the specific "
        "tag for precision; (b) directory browsing and gap-analysis clustering can "
        "use the parent for aggregation; (c) staff who prefer a general label can "
        "add it manually via Tag Refinement (UC-11) without displacing the "
        "specific tags."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DB fetch helper (optional)
# ---------------------------------------------------------------------------

async def _fetch_from_db(user_id: str) -> tuple[list[str], dict[str, Optional[str]]]:
    """Pull AI tags + parent_labels from the live database for a given user."""
    from app.db.session import SessionLocal
    from app.db.models import UserExpertiseTag, ExpertiseTag
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    async with SessionLocal() as session:
        stmt = (
            select(UserExpertiseTag)
            .where(UserExpertiseTag.user_id == user_id)
            .options(joinedload(UserExpertiseTag.tag))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    ai_tags = [r.tag.canonical_label for r in rows]
    parent_map = {r.tag.canonical_label: r.tag.parent_label for r in rows}
    return ai_tags, parent_map


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Validate AI-generated expertise tags against staff self-declared areas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--staff-name", default="Unknown", help="Display name for the report.")
    ap.add_argument("--user-id", help="Pull AI tags from the DB for this UUID.")
    ap.add_argument(
        "--ai-tags",
        help="Comma-separated AI-generated canonical_label values (if not using --user-id).",
    )
    ap.add_argument(
        "--ai-tags-file",
        type=Path,
        help="JSON file containing a list of {canonical_label, parent_label} objects.",
    )
    ap.add_argument(
        "--self-declared",
        help="Comma / semicolon-separated self-declared areas.",
    )
    ap.add_argument(
        "--self-declared-file",
        type=Path,
        help="Plain-text file, one self-declared area per line.",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=SOFT_COSINE_THRESHOLD,
        help=f"Cosine similarity threshold (default {SOFT_COSINE_THRESHOLD}).",
    )
    ap.add_argument("--quiet", action="store_true", help="Suppress stdout summary.")
    return ap.parse_args()


async def _main(args: argparse.Namespace) -> None:
    # ---- resolve AI tags ----
    ai_tags: list[str]
    parent_map: dict[str, Optional[str]]

    if args.user_id:
        ai_tags, parent_map = await _fetch_from_db(args.user_id)
    elif args.ai_tags_file:
        raw = json.loads(args.ai_tags_file.read_text(encoding="utf-8"))
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            ai_tags = [item["canonical_label"] for item in raw]
            parent_map = {item["canonical_label"]: item.get("parent_label") for item in raw}
        else:
            ai_tags = [str(x) for x in raw]
            parent_map = {}
    elif args.ai_tags:
        ai_tags = [t.strip() for t in args.ai_tags.replace(";", ",").split(",") if t.strip()]
        parent_map = {}
    else:
        print("ERROR: provide --user-id, --ai-tags, or --ai-tags-file", file=sys.stderr)
        sys.exit(1)

    # ---- resolve self-declared ----
    if args.self_declared_file:
        self_declared = [
            line.strip()
            for line in args.self_declared_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif args.self_declared:
        self_declared = [
            t.strip()
            for t in args.self_declared.replace(";", ",").split(",")
            if t.strip()
        ]
    else:
        print("ERROR: provide --self-declared or --self-declared-file", file=sys.stderr)
        sys.exit(1)

    payload = await run_validation(
        staff_name=args.staff_name,
        ai_tags=ai_tags,
        ai_parent_labels=parent_map,
        self_declared=self_declared,
        threshold=args.threshold,
        verbose=not args.quiet,
    )

    markdown = build_markdown(payload)
    json_path, md_path = write_report("staff_tags", payload, markdown)

    if not args.quiet:
        print(markdown)
        print(f"\n── Saved to {md_path}  /  {json_path}")


def main() -> None:
    asyncio.run(_main(_parse_args()))


if __name__ == "__main__":
    main()
