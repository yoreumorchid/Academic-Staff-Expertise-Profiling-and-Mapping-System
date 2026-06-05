"""Study 5 — Time-on-task / efficiency comparison.

Reads ``datasets/efficiency.csv`` (see ../README.md §5), computes mean
and standard deviation per mode (manual vs system) and reports the
speed-up factor.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

from evaluation.scripts._common import write_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("evaluation/datasets/efficiency.csv"))
    args = parser.parse_args()

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("efficiency.csv is empty.")

    by_mode: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_mode[r["mode"].strip().lower()].append(r)

    if "manual" not in by_mode or "system" not in by_mode:
        raise SystemExit("Need rows with mode='manual' and mode='system'.")

    def summarise(mode_rows: list[dict]) -> dict:
        times = [float(r["time_seconds"]) for r in mode_rows]
        tags = [float(r["tags_produced"]) for r in mode_rows]
        loads = [float(r["subjective_load"]) for r in mode_rows]
        return {
            "n_observations": len(mode_rows),
            "time_seconds_mean": round(mean(times), 2),
            "time_seconds_stdev": round(pstdev(times), 2),
            "tags_mean": round(mean(tags), 2),
            "subjective_load_mean": round(mean(loads), 2),
        }

    manual = summarise(by_mode["manual"])
    system = summarise(by_mode["system"])
    speedup = manual["time_seconds_mean"] / system["time_seconds_mean"] if system["time_seconds_mean"] else 0
    tag_ratio = system["tags_mean"] / manual["tags_mean"] if manual["tags_mean"] else 0

    payload = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "csv_path": str(args.csv),
        "manual": manual,
        "system": system,
        "speedup_factor": round(speedup, 2),
        "tag_yield_ratio": round(tag_ratio, 2),
        "passes_acceptance": speedup >= 5.0,
    }

    md = (
        "# Efficiency & Cost-Benefit Report\n\n"
        f"* Generated: {payload['generated_at']}\n\n"
        "| Mode | Mean time (s) | Stdev | Mean tags | Subjective load |\n"
        "|---|---|---|---|---|\n"
        f"| Manual | {manual['time_seconds_mean']} | {manual['time_seconds_stdev']} | {manual['tags_mean']} | {manual['subjective_load_mean']} |\n"
        f"| System | {system['time_seconds_mean']} | {system['time_seconds_stdev']} | {system['tags_mean']} | {system['subjective_load_mean']} |\n\n"
        f"Speed-up: **{payload['speedup_factor']}×** (target ≥ 5× — "
        f"{'PASS' if payload['passes_acceptance'] else 'FAIL'})\n\n"
        f"Tag-yield ratio (system / manual): {payload['tag_yield_ratio']}×\n"
    )
    json_path, md_path = write_report("efficiency", payload, md)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
