"""Codabench **scoring program** for the WFLO assignment.

Reads the predictions produced by ``ingestion.py`` and turns them into a single
score, written to ``<output_dir>/scores.json``.

Scoring rule
------------
For every instance the score is the expected power achieved relative to a
reference power, capped at 1:

* **infeasible** layouts (overlapping turbines, turbines outside the terrain or
  inside an exclusion zone) score **0**;
* otherwise ``score = min(1, expected_power / reference_power)``, where
  ``reference_power`` is taken from the reference data when available, and
  otherwise from the wake-free upper bound recorded by the ingestion program.

The final score is the mean over all instances.

Codabench invocation (positional arguments)::

    python score.py <input_dir> <output_dir>

Local test (after running ``ingestion.py``)::

    uv run python -m wind_farm_layout_optimization.autograder.score /tmp/wflo_out /tmp/wflo_scores
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_predictions(input_dir: Path) -> dict:
    """Predictions live in ``input/res/predictions.json`` on Codabench."""
    for candidate in (input_dir / "res" / "predictions.json", input_dir / "predictions.json"):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise SystemExit(f"no predictions.json found under {input_dir}")


def load_reference(input_dir: Path) -> dict:
    """Optional reference data in ``input/ref/reference.json``."""
    for candidate in (input_dir / "ref" / "reference.json", input_dir / "reference.json"):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def compute_scores(predictions: dict, reference: dict) -> tuple[float, dict]:
    per_instance: dict[str, float] = {}
    for name, pred in predictions.get("instances", {}).items():
        if not pred.get("feasible"):
            per_instance[name] = 0.0
            continue
        reference_power = (
            reference.get(name, {}).get("expected_power_mw")
            or pred.get("reference_power_mw")
        )
        power = pred.get("expected_power_mw", 0.0)
        per_instance[name] = min(1.0, power / reference_power) if reference_power else 0.0
    mean = sum(per_instance.values()) / len(per_instance) if per_instance else 0.0
    return mean, per_instance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench scoring program (WFLO).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> float:
    args = parse_args(argv)
    predictions = load_predictions(args.input_dir)
    reference = load_reference(args.input_dir)

    score, per_instance = compute_scores(predictions, reference)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores = {"score": score, "instances": per_instance}
    (args.output_dir / "scores.json").write_text(
        json.dumps(scores, indent=2), encoding="utf-8"
    )

    print("Per-instance scores:")
    for name, value in per_instance.items():
        print(f"  - {name}: {value:.4f}")
    print(f"Final score: {score:.4f}")
    print(f"Wrote {args.output_dir / 'scores.json'}")
    return score


if __name__ == "__main__":
    main()
