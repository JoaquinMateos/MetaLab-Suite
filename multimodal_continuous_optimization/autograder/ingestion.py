"""Codabench **ingestion program** for the MMCO assignment.

For every terrain it runs the submitted solver against the environment and
enforces the two hard limits of this problem:

* a **wall-clock timeout** (``--time-limit``) and a **CPU-time timeout**
  (``--cpu-limit``), both monitored in-process with ``signal.setitimer``;
* the **maximum evaluation budget**, enforced by the environment itself
  (a solver that evaluates past the budget is *cut*).

A run that times out, exceeds the budget or crashes is recorded as **invalid**
(``score.py`` then charges a severe penalty).

Output: ``<output_dir>/predictions.json``.

Codabench invocation (positional arguments)::

    python ingestion.py <input_dir> <output_dir> <submission_dir>

Local test (from the repository root)::

    uv run python -m multimodal_continuous_optimization.autograder.ingestion \
        multimodal_continuous_optimization /tmp/mmco_out \
        multimodal_continuous_optimization/random_search_mmco.py
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import signal
import sys
import time
from pathlib import Path
from types import ModuleType

from multimodal_continuous_optimization.given.simulator_mmco import (
    EvaluationBudgetExceeded,
    Instance,
    SignalEnvironment,
)
from multimodal_continuous_optimization.student_mmco import BaseSolver, BudgetExhausted


class SolverTimeout(Exception):
    """Raised when a solver exceeds its wall-clock or CPU-time budget."""


# ---------------------------------------------------------------------------
# Discovery / loading
# ---------------------------------------------------------------------------
def find_instances(input_dir: Path) -> list[Path]:
    for sub in (input_dir / "instances", input_dir):
        if sub.is_dir():
            files = sorted(p for p in sub.glob("*.json") if not p.name.startswith("."))
            if files:
                return files
    return []


def find_submission(submission_dir: Path) -> Path | None:
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
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if "BaseSolver" in text or "def solve" in text:
            return candidate
    return candidates[0] if candidates else None


def load_module(path: Path) -> ModuleType:
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"submission_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_solver_class(module: ModuleType) -> type[BaseSolver]:
    """Return the first concrete :class:`BaseSolver` subclass in the submission."""
    for value in vars(module).values():
        if (
            isinstance(value, type)
            and issubclass(value, BaseSolver)
            and value is not BaseSolver
            and not inspect.isabstract(value)
        ):
            return value
    raise ValueError("submission defines no concrete BaseSolver subclass")


# ---------------------------------------------------------------------------
# Time limits (wall-clock + CPU)
# ---------------------------------------------------------------------------
def run_with_limits(solver: BaseSolver, wall_limit: float, cpu_limit: float) -> None:
    """Run ``solver.solve()`` under a wall-clock and a CPU-time limit."""

    def _on_wall(signum, frame):  # pragma: no cover - signal handler
        raise SolverTimeout(f"wall-clock limit of {wall_limit:g}s exceeded")

    def _on_cpu(signum, frame):  # pragma: no cover - signal handler
        raise SolverTimeout(f"CPU-time limit of {cpu_limit:g}s exceeded")

    old_wall = signal.signal(signal.SIGALRM, _on_wall)
    old_cpu = signal.signal(signal.SIGPROF, _on_cpu)
    signal.setitimer(signal.ITIMER_REAL, wall_limit)
    signal.setitimer(signal.ITIMER_PROF, cpu_limit)
    try:
        solver.solve()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGALRM, old_wall)
        signal.signal(signal.SIGPROF, old_cpu)


def run_solver(
    instance: Instance,
    solver_cls: type[BaseSolver],
    wall_limit: float,
    cpu_limit: float,
    seed: int,
) -> dict:
    """Run one solver against one terrain and return a prediction record."""
    started = time.perf_counter()
    env = SignalEnvironment(instance, strict_budget=True)
    record: dict = {
        "dimension": instance.dimension,
        "bounds": list(instance.bounds),
        "optimum": list(instance.optimum),
        "budget": env.budget,
        "evaluations": 0,
        "budget_exceeded": False,
        "best_x": None,
        "valid": False,
        "reason": None,
    }

    try:
        solver = solver_cls(
            evaluate=env.evaluate,
            dimension=instance.dimension,
            lower=instance.lower,
            upper=instance.upper,
            budget=instance.max_evaluations,
            seed=seed,
        )
    except Exception as exc:  # noqa: BLE001 - a bad submission must not crash the grader
        record["reason"] = f"solver construction failed: {type(exc).__name__}: {exc}"
        record["runtime_s"] = time.perf_counter() - started
        return record

    try:
        run_with_limits(solver, wall_limit, cpu_limit)
        if solver.best_x is None:
            record["reason"] = "solver returned no solution"
        elif env.budget_exceeded:
            record["reason"] = "evaluation budget exceeded"
        else:
            record["best_x"] = [float(v) for v in solver.best_x]
            record["valid"] = True
    except (EvaluationBudgetExceeded, BudgetExhausted) as exc:
        record["reason"] = f"budget: {exc}"
        record["budget_exceeded"] = True
    except SolverTimeout as exc:
        record["reason"] = f"timeout: {exc}"
    except Exception as exc:  # noqa: BLE001 - any submission crash invalidates the solution
        record["reason"] = f"crash: {type(exc).__name__}: {exc}"
    finally:
        record["evaluations"] = env.evaluations
        record["budget_exceeded"] = record["budget_exceeded"] or env.budget_exceeded
        record["runtime_s"] = time.perf_counter() - started
    return record


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------
def run(
    input_dir: Path,
    output_dir: Path,
    submission_dir: Path,
    wall_limit: float = 60.0,
    cpu_limit: float = 60.0,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    instances = find_instances(input_dir)
    submission = find_submission(submission_dir)
    if submission is None:
        raise SystemExit(f"no submission found in {submission_dir}")
    if not instances:
        raise SystemExit(f"no instance JSON found under {input_dir}")

    print(f"Ingestion: {len(instances)} instance(s), submission = {submission}")
    module = load_module(submission)
    try:
        solver_cls = find_solver_class(module)
    except Exception as exc:  # noqa: BLE001
        solver_cls = None
        solver_error = str(exc)

    predictions: dict[str, dict] = {}
    for index, instance_path in enumerate(instances):
        instance = Instance.load(instance_path)
        name = instance.name
        if solver_cls is None:
            predictions[name] = {
                "dimension": instance.dimension, "bounds": list(instance.bounds),
                "optimum": list(instance.optimum), "budget": instance.max_evaluations,
                "evaluations": 0, "budget_exceeded": False, "best_x": None,
                "valid": False, "reason": f"solver error: {solver_error}", "runtime_s": 0.0,
            }
            print(f"  - {name}: SOLVER ERROR ({solver_error})")
            continue

        record = run_solver(instance, solver_cls, wall_limit, cpu_limit, seed=index)
        predictions[name] = record
        print(f"  - {name}: valid={record['valid']} "
              f"evaluations={record['evaluations']}/{record['budget']} "
              f"({record['runtime_s']:.2f}s)"
              + (f"  [{record['reason']}]" if record["reason"] else ""))

    (output_dir / "predictions.json").write_text(
        json.dumps({"instances": predictions}, indent=2), encoding="utf-8"
    )
    print(f"Wrote {output_dir / 'predictions.json'}")
    return predictions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench ingestion program (MMCO).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    parser.add_argument("submission_dir", nargs="?", type=Path, default=Path("/app/submission"))
    parser.add_argument("--time-limit", type=float, default=60.0, help="wall-clock seconds")
    parser.add_argument("--cpu-limit", type=float, default=60.0, help="CPU seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run(args.input_dir, args.output_dir, args.submission_dir,
        wall_limit=args.time_limit, cpu_limit=args.cpu_limit)


if __name__ == "__main__":
    main()
