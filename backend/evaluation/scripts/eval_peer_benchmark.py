"""Calibrate provisional UC-16 distance bands on the synthetic development set."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from app.services.embeddings import embed_texts

LABELS = ["covered", "partially_covered", "candidate_gap"]


def classify(distance: float, covered_max: float, partial_max: float) -> str:
    if distance <= covered_max:
        return "covered"
    if distance <= partial_max:
        return "partially_covered"
    return "candidate_gap"


def select_thresholds(distances: list[float], expected: list[str]) -> tuple[float, float, float]:
    best = (-1.0, 0.0, 0.0)
    for covered_step in range(5, 61):
        covered_max = covered_step / 100
        for partial_step in range(covered_step + 1, 81):
            partial_max = partial_step / 100
            predicted = [classify(value, covered_max, partial_max) for value in distances]
            score = float(f1_score(expected, predicted, labels=LABELS, average="macro", zero_division=0))
            candidate = (score, -covered_max, -partial_max)
            incumbent = (best[0], -best[1], -best[2])
            if candidate > incumbent:
                best = (score, covered_max, partial_max)
    return best


async def evaluate(dataset_path: Path) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    staff = dataset["staff_capabilities"]
    segments = dataset["peer_segments"]
    vectors = await embed_texts([
        *(item["text"] for item in staff),
        *(item["text"] for item in segments),
    ])
    staff_vectors = np.asarray(vectors[:len(staff)], dtype=float)
    segment_vectors = np.asarray(vectors[len(staff):], dtype=float)
    similarities = segment_vectors @ staff_vectors.T
    nearest = np.argmax(similarities, axis=1)
    distances = [float(1.0 - similarities[index, staff_index]) for index, staff_index in enumerate(nearest)]
    expected = [item["label"] for item in segments]
    macro_f1, covered_max, partial_max = select_thresholds(distances, expected)
    predicted = [classify(value, covered_max, partial_max) for value in distances]
    rows = [
        {
            "id": segment["id"],
            "expected": segment["label"],
            "predicted": prediction,
            "distance": distance,
            "nearest_staff": staff[int(staff_index)]["id"],
        }
        for segment, prediction, distance, staff_index in zip(segments, predicted, distances, nearest)
    ]
    return {
        "dataset_id": dataset["dataset_id"],
        "provenance": dataset["provenance"],
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "formula": "1 - cosine_similarity(peer_segment, nearest_staff_capability)",
        "selected_thresholds": {
            "covered_max": covered_max,
            "partially_covered_max": partial_max,
        },
        "macro_f1": macro_f1,
        "classification_report": classification_report(
            expected, predicted, labels=LABELS, output_dict=True, zero_division=0
        ),
        "confusion_matrix_labels": LABELS,
        "confusion_matrix": confusion_matrix(expected, predicted, labels=LABELS).tolist(),
        "rows": rows,
        "limitation": "Synthetic development calibration; faculty-labelled real examples are required before accuracy claims.",
    }


def render_markdown(payload: dict) -> str:
    thresholds = payload["selected_thresholds"]
    lines = [
        "# UC-16 Synthetic Threshold Calibration",
        "",
        f"- Dataset: `{payload['dataset_id']}`",
        f"- Model: `{payload['embedding_model']}`",
        f"- Covered: distance <= {thresholds['covered_max']:.2f}",
        f"- Partially covered: distance <= {thresholds['partially_covered_max']:.2f}",
        f"- Macro F1: {payload['macro_f1']:.3f}",
        "- Status: provisional; pending faculty-labelled UAT calibration",
        "",
        "| Segment | Expected | Predicted | Distance | Nearest synthetic staff |",
        "|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {row['id']} | {row['expected']} | {row['predicted']} | {row['distance']:.3f} | {row['nearest_staff']} |"
        for row in payload["rows"]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/datasets/peer_benchmark_synthetic.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/reports"))
    args = parser.parse_args()
    payload = asyncio.run(evaluate(args.dataset))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / f"peer_benchmark_calibration_{timestamp}"
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "report": str(stem.with_suffix('.json')),
        "thresholds": payload["selected_thresholds"],
        "macro_f1": payload["macro_f1"],
    }))


if __name__ == "__main__":
    main()
