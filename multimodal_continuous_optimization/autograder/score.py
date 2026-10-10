"""Codabench **scoring program** for the MMCO assignment.

Reads the predictions produced by ``ingestion.py`` and turns them into a single
score, written to ``<output_dir>/scores.json``.

Scoring rule (lower is better)
------------------------------
For every terrain the error is the **normalised Euclidean distance** between the
best coordinates the student reported and the **hidden true global optimum** of
the instance::

    error = || best_x - optimum || / ( sqrt(n) * (upper - lower) )

so ``0`` means "found the signal exactly" and ``1`` is the worst possible point
in the domain. The reported score is the **mean** over terrains.

Battery---er, *rules*---are enforced relentlessly: if a prediction is marked
invalid (timeout, evaluation budget exceeded, crash) it is charged a **severe
penalty**, so a rule-breaking run can never beat an honest one.

Codabench invocation (positional arguments)::

    python score.py <input_dir> <output_dir>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SEVERE_PENALTY = 1e9


def load_predictions(input_dir: Path) -> dict:
    """Predictions live in ``input/res/`` on Codabench (JSON or legacy ``.txt``)."""
    for candidate in (
        input_dir / "res" / "predictions.json",
        input_dir / "predictions.json",
        input_dir / "res" / "predictions.txt",
        input_dir / "predictions.txt",
    ):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise SystemExit(f"no predictions file found under {input_dir}")


def load_reference(input_dir: Path) -> dict:
    """Optional reference instances (with the hidden optimum) in ``input/ref/``."""
    for sub in (input_dir / "ref", input_dir / "instances", input_dir):
        if sub.is_dir():
            reference: dict[str, dict] = {}
            for path in sorted(sub.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and "optimum" in data and "name" in data:
                    reference[data["name"]] = data
            if reference:
                return reference
    return {}


def normalized_error(best_x, optimum, dimension: int, bounds) -> float:
    """Distance from ``best_x`` to the optimum, scaled to ``[0, 1]``."""
    if not best_x or not optimum or len(best_x) != len(optimum):
        return 1.0
    distance = math.dist(best_x, optimum)
    span = float(bounds[1]) - float(bounds[0])
    denominator = math.sqrt(max(1, int(dimension))) * span
    if denominator <= 0:
        return 1.0
    return min(1.0, distance / denominator)


def compute_scores(predictions: dict, reference: dict) -> tuple[float, dict]:
    per_instance: dict[str, float] = {}
    for name, prediction in predictions.get("instances", {}).items():
        if not prediction.get("valid"):
            per_instance[name] = SEVERE_PENALTY
            continue
        ref = reference.get(name, {})
        optimum = ref.get("optimum") or prediction.get("optimum")
        dimension = prediction.get("dimension") or ref.get("dimension") or len(optimum or [])
        bounds = prediction.get("bounds") or ref.get("bounds") or [0.0, 1.0]
        per_instance[name] = normalized_error(
            prediction.get("best_x"), optimum, dimension, bounds
        )
    score = (
        sum(per_instance.values()) / len(per_instance) if per_instance else SEVERE_PENALTY
    )
    return score, per_instance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench scoring program (MMCO).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> float:
    args = parse_args(argv)
    predictions = load_predictions(args.input_dir)
    reference = load_reference(args.input_dir)

    score, per_instance = compute_scores(predictions, reference)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "scores.json").write_text(
        json.dumps({"score": score, "instances": per_instance}, indent=2), encoding="utf-8"
    )

    print("Per-instance error (lower is better; 1e9 = invalid / penalised):")
    for name, value in per_instance.items():
        label = "invalid" if value >= SEVERE_PENALTY else f"{value:.6g}"
        print(f"  - {name}: {label}")
    print(f"Final score: {score:.6g}")
    print(f"Wrote {args.output_dir / 'scores.json'}")
    return score


if __name__ == "__main__":
    main()
