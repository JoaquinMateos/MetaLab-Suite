"""Codabench **scoring program** for the DDRP assignment.

Reads the predictions produced by ``ingestion.py`` and turns them into a single
score, written to ``<output_dir>/scores.json``.

Scoring rule (lower is better)
------------------------------
For every workday the cost is

    cost = Distance + (Unserved x 1000) + (Swaps x 10)

and the reported score is the **sum of the per-instance costs**. Battery life is
validated relentlessly: a solution is **invalid** --- and therefore charged a
huge penalty instead of its cost --- if the ingestion run crashed, timed out, or
produced any battery, payload or range violation. In other words, a plan whose
drones run out of charge can never beat a feasible one.

Codabench invocation (positional arguments)::

    python score.py <input_dir> <output_dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

INVALID_PENALTY = 1e9
UNSERVED_WEIGHT = 1000.0
SWAP_WEIGHT = 10.0


def load_predictions(input_dir: Path) -> dict:
    """Predictions live in ``input/res/predictions.json`` on Codabench."""
    for candidate in (input_dir / "res" / "predictions.json", input_dir / "predictions.json"):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise SystemExit(f"no predictions.json found under {input_dir}")


def is_valid(prediction: dict) -> bool:
    """A solution is valid only if it respects every physical constraint."""
    if not prediction.get("valid"):
        return False
    return not (
        prediction.get("battery_violations")
        or prediction.get("payload_violations")
        or prediction.get("range_violations")
    )


def instance_cost(prediction: dict) -> float:
    """``Distance + 1000 x Unserved + 10 x Swaps``."""
    return (
        prediction.get("distance", 0.0)
        + UNSERVED_WEIGHT * prediction.get("unserved", 0)
        + SWAP_WEIGHT * prediction.get("swaps", 0)
    )


def compute_scores(predictions: dict) -> tuple[float, dict]:
    per_instance: dict[str, float] = {}
    for name, prediction in predictions.get("instances", {}).items():
        per_instance[name] = (
            instance_cost(prediction) if is_valid(prediction) else INVALID_PENALTY
        )
    total = sum(per_instance.values())
    return total, per_instance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench scoring program (DDRP).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> float:
    args = parse_args(argv)
    predictions = load_predictions(args.input_dir)

    total, per_instance = compute_scores(predictions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores = {"score": total, "instances": per_instance}
    (args.output_dir / "scores.json").write_text(
        json.dumps(scores, indent=2), encoding="utf-8"
    )

    print("Per-instance cost (lower is better; 1e9 = invalid):")
    for name, value in per_instance.items():
        label = "invalid" if value >= INVALID_PENALTY else f"{value:.1f}"
        print(f"  - {name}: {label}")
    print(f"Total score: {total:.1f}")
    print(f"Wrote {args.output_dir / 'scores.json'}")
    return total


if __name__ == "__main__":
    main()
