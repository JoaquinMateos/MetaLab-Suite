"""Codabench **ingestion program** for the WFLO assignment.

This is the backend that runs a submitted solver over every test instance and
produces the predictions consumed by ``score.py``. For each instance it

1. runs the solver in a subprocess under a **strict CPU + wall timeout**,
2. verifies the physical constraints (inside terrain, outside exclusion zones,
   and --- crucially --- no overlapping turbines given the minimum spacing), and
3. evaluates the expected power with the reference simulator.

Output: ``<output_dir>/predictions.json``.

Codabench invocation (positional arguments)::

    python ingestion.py <input_dir> <output_dir> <submission_dir>

Local test (from the repository root)::

    uv run python -m wind_farm_layout_optimization.ingestion \
        wind_farm_layout_optimization /tmp/wflo_out wind_farm_layout_optimization/student_wflo.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wind_farm_layout_optimization.simulator_wflo import WindFarmEnvironment
from wind_farm_layout_optimization.student_wflo import run_solver_script


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def find_instances(input_dir: Path) -> list[Path]:
    """All instance JSON files, preferring an ``instances/`` sub-directory."""
    for sub in (input_dir / "instances", input_dir):
        if sub.is_dir():
            files = sorted(p for p in sub.glob("*.json") if not p.name.startswith("."))
            if files:
                return files
    return []


def find_solver(submission_dir: Path) -> Path | None:
    """Locate the solver script inside the submission."""
    if submission_dir.is_file():
        return submission_dir
    if not submission_dir.is_dir():
        return None
    preferred = submission_dir / "solver.py"
    if preferred.exists():
        return preferred
    candidates = [p for p in sorted(submission_dir.glob("*.py")) if p.name != "__init__.py"]
    for candidate in candidates:
        try:
            if "BaseWFLOSolver" in candidate.read_text(encoding="utf-8"):
                return candidate
        except OSError:
            continue
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------
def run(
    input_dir: Path,
    output_dir: Path,
    submission_dir: Path,
    time_limit: float = 60.0,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    instances = find_instances(input_dir)
    solver = find_solver(submission_dir)
    if solver is None:
        raise SystemExit(f"no solver script found in submission dir: {submission_dir}")
    if not instances:
        raise SystemExit(f"no instance JSON files found under: {input_dir}")

    print(f"Ingestion: {len(instances)} instance(s), solver = {solver}")
    predictions: dict[str, dict] = {}

    for index, instance_path in enumerate(instances):
        env = WindFarmEnvironment.from_file(instance_path)
        name = env.instance.name
        out = output_dir / f"_layout_{name}.json"

        outcome = run_solver_script(
            solver, instance_path, out, seed=index,
            wall_limit=time_limit, cpu_limit=time_limit,
        )
        if not outcome["ok"]:
            print(f"  - {name}: FAILED ({outcome['error']})")
            predictions[name] = {
                "feasible": False,
                "error": outcome["error"],
                "expected_power_mw": 0.0,
                "reference_power_mw": _reference_power(env),
                "runtime_s": outcome["runtime_s"],
            }
            continue

        layout = outcome["result"].get("layout", [])
        report = env.evaluate(layout)
        predictions[name] = {
            "layout": layout,
            "expected_power_mw": report["expected_power_mw"],
            "expected_efficiency": report["expected_efficiency"],
            "reference_power_mw": _reference_power(env),
            "feasible": report["feasible"],
            "outside_terrain": report["outside_terrain"],
            "inside_exclusion": report["inside_exclusion"],
            "spacing_violations": report["spacing_violations"],
            "runtime_s": outcome["runtime_s"],
        }
        print(
            f"  - {name}: power={report['expected_power_mw']:.2f} MW "
            f"feasible={report['feasible']} ({outcome['runtime_s']:.2f}s)"
        )

    (output_dir / "predictions.json").write_text(
        json.dumps({"instances": predictions}, indent=2), encoding="utf-8"
    )
    print(f"Wrote {output_dir / 'predictions.json'}")
    return predictions


def _reference_power(env: WindFarmEnvironment) -> float:
    """Wake-free expected power --- an upper bound used to normalise scores."""
    rose = env.instance.wind_rose
    total_weight = sum(s.probability for s in rose) or 1.0
    return sum(
        (s.probability / total_weight) * env.ideal_power_mw(s) for s in rose
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench ingestion program (WFLO).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    parser.add_argument("submission_dir", nargs="?", type=Path, default=Path("/app/submission"))
    parser.add_argument("--time-limit", type=float, default=60.0, help="CPU + wall timeout (s)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run(args.input_dir, args.output_dir, args.submission_dir, time_limit=args.time_limit)


if __name__ == "__main__":
    main()
