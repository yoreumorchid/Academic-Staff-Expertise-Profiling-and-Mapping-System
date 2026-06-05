"""Study 4 — UMExpert vs. ExpertiseInsight coverage uplift.

Consumes ``datasets/profile_completion.csv`` (see ../README.md §4).
Computes per-staff coverage uplift, recency uplift and aggregate
completeness, plus the sync job success rate over the last N days
straight from the DB so you do not need to copy that figure manually.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from sqlalchemy import func, select

from app.db.models import SyncJob, SyncJobStatus
from app.db.session import async_session_factory
from evaluation.scripts._common import split_tag_list, write_report


async def _sync_success_rate(days: int) -> dict[str, float | int]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with async_session_factory() as session:
        total = await session.scalar(
            select(func.count(SyncJob.id)).where(SyncJob.created_at >= since)
        )
        succeeded = await session.scalar(
            select(func.count(SyncJob.id)).where(
                SyncJob.created_at >= since,
                SyncJob.status == SyncJobStatus.SUCCEEDED,
            )
        )
        total = total or 0
        succeeded = succeeded or 0
        return {
            "window_days": days,
            "total_jobs": total,
            "succeeded_jobs": succeeded,
            "success_rate": round(succeeded / total, 4) if total else 0.0,
        }


def _staff_uplift(row: dict) -> dict:
    ume = set(split_tag_list(row.get("umexpert_interests", "")))
    sys = set(split_tag_list(row.get("system_tags", "")))
    new_in_sys = sys - ume
    uplift = (len(new_in_sys) / len(ume)) if ume else float(len(sys))

    try:
        ume_year = int(row.get("umexpert_latest_year") or 0)
        sys_year = int(row.get("system_latest_year") or 0)
    except ValueError:
        ume_year, sys_year = 0, 0

    return {
        "staff_id": row["staff_id"],
        "staff_name": row.get("staff_name", ""),
        "umexpert_tags": len(ume),
        "system_tags": len(sys),
        "new_tags": len(new_in_sys),
        "coverage_uplift": round(uplift, 3),
        "recency_uplift_years": sys_year - ume_year,
    }


async def main_async(csv_path: Path, window_days: int) -> None:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("profile_completion.csv is empty.")

    per_staff = [_staff_uplift(r) for r in rows]
    avg_uplift = mean(s["coverage_uplift"] for s in per_staff)
    completeness = sum(1 for s in per_staff if s["system_tags"] >= 5) / len(per_staff)
    avg_recency = mean(s["recency_uplift_years"] for s in per_staff)

    sync = await _sync_success_rate(window_days)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "csv_path": str(csv_path),
        "n_staff": len(per_staff),
        "avg_coverage_uplift": round(avg_uplift, 3),
        "completeness_ge5_tags": round(completeness, 3),
        "avg_recency_uplift_years": round(avg_recency, 3),
        "sync_jobs": sync,
        "per_staff": per_staff,
    }

    md = (
        "# Data Reliability & Sync Coverage Report\n\n"
        f"* Generated: {payload['generated_at']}\n"
        f"* Staff sampled: {payload['n_staff']}\n\n"
        "| Metric | Value | Target |\n|---|---|---|\n"
        f"| Avg coverage uplift vs UMExpert | **{payload['avg_coverage_uplift']:.2f}×** | ≥ 1.00× |\n"
        f"| Completeness (≥5 tags) | {payload['completeness_ge5_tags']:.0%} | ≥ 80% |\n"
        f"| Avg recency uplift | {payload['avg_recency_uplift_years']} years | ≥ 0 |\n"
        f"| Sync success rate (last {window_days}d) | {sync['success_rate']:.0%} ({sync['succeeded_jobs']}/{sync['total_jobs']}) | ≥ 95% |\n"
    )
    json_path, md_path = write_report("sync_coverage", payload, md)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv", type=Path, default=Path("evaluation/datasets/profile_completion.csv")
    )
    parser.add_argument("--window-days", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main_async(args.csv, args.window_days))


if __name__ == "__main__":
    main()
