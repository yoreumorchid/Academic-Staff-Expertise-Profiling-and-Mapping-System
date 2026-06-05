"""Common helpers for evaluation scripts.

Centralised so every study reports paths, timestamps and metric tables
the same way.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

EVAL_ROOT = Path(__file__).resolve().parent.parent
DATASETS = EVAL_ROOT / "datasets"
REPORTS = EVAL_ROOT / "reports"


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def write_report(name: str, payload: dict[str, Any], markdown: str) -> tuple[Path, Path]:
    """Persist a JSON + Markdown pair under ``reports/``."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"{name}_{timestamp()}"
    json_path = REPORTS / f"{stem}.json"
    md_path = REPORTS / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")


def canonicalise(tag: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace, drop trailing 's'."""
    s = _NORMALIZE_RE.sub(" ", tag.lower())
    s = " ".join(s.split())
    if s.endswith(" s"):  # accidental " s" suffix from punctuation strip
        s = s[:-2]
    if s.endswith("s") and len(s) > 3 and not s.endswith("ss"):
        s = s[:-1]
    return s


def split_tag_list(value: str | Iterable[str]) -> list[str]:
    """Accept either a list or a separator-delimited string."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[;,|]", value)
    else:
        parts = list(value)
    return [canonicalise(p) for p in parts if p and str(p).strip()]


def f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def jsonl_lines(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
