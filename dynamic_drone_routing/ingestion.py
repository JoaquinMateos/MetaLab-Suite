"""Codabench **ingestion program** for the DDRP assignment.

For every workday it runs the submitted dispatch policy inside the SimPy engine
and produces the predictions consumed by ``score.py``. Key features:

* **CPU timeout per dynamic event.** Every call to the policy (one per
  re-optimisation, i.e. at ``t = 0`` and at each dynamic arrival) is bounded by
  ``--per-event-cpu`` seconds of *CPU time* using ``signal.setitimer`` with
  ``ITIMER_PROF``. A policy that burns too much CPU in a single event aborts the
  run and the instance is marked invalid.
* A **total wall-clock budget** bounds the whole workday.
* A run that crashes, times out or violates the battery/payload/range limits is
  recorded as **invalid** (``score.py`` then penalises it).

Output: ``<output_dir>/predictions.json``.

Codabench invocation (positional arguments)::

    python ingestion.py <input_dir> <output_dir> <submission_dir>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
import time
from pathlib import Path
from types import ModuleType

from dynamic_drone_routing.simulator_ddrp import Instance, SimulationEnvironment

INVALID_PENALTY = 1e9


class EventTimeout(Exception):
    """Raised when a single re-optimisation exceeds its CPU budget."""


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
            if "reoptimize" in text or "BaseSolver" in text:
                return candidate
        except OSError:
            continue
    return candidates[0] if candidates else None


def load_module(path: Path) -> ModuleType:
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"submission_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_policy(module: ModuleType, instance: Instance, seed: int):
    """Find the dispatch policy in the submission module."""
    if hasattr(module, "build_policy"):
        return module.build_policy(instance, seed=seed)
    for value in vars(module).values():
        if isinstance(value, type) and callable(getattr(value, "reoptimize", None)):
            return value(instance, seed=seed).reoptimize
    if callable(getattr(module, "reoptimize", None)):
        return module.reoptimize
    raise ValueError("submission defines no policy (no build_policy, solver class or reoptimize)")


# ---------------------------------------------------------------------------
# Per-event CPU-time enforcement
# ---------------------------------------------------------------------------
def make_timed_policy(policy, per_event_cpu: float):
    """Wrap a policy so each call gets a strict CPU-time budget."""

    def _on_prof(signum, frame):  # pragma: no cover - signal handler
        raise EventTimeout(f"reoptimisation exceeded {per_event_cpu:g}s of CPU")

    def wrapped(state):
        previous = signal.signal(signal.SIGPROF, _on_prof)
        signal.setitimer(signal.ITIMER_PROF, per_event_cpu)
        try:
            return policy(state)
        finally:
            signal.setitimer(signal.ITIMER_PROF, 0)
            signal.signal(signal.SIGPROF, previous)

    return wrapped


def run_instance(
    instance: Instance,
    policy,
    per_event_cpu: float,
    total_wall: float,
    seed: int,
) -> dict:
    started = time.perf_counter()
    result = {
        "valid": False, "reason": None, "distance": 0.0, "unserved": 0,
        "swaps": 0, "served": 0, "battery_violations": 0, "payload_violations": 0,
        "range_violations": 0, "makespan": 0.0,
    }

    def _on_alarm(signum, frame):  # pragma: no cover - signal handler
        raise EventTimeout(f"workday exceeded the {total_wall:g}s wall budget")

    previous_alarm = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, total_wall)
    try:
        sim = SimulationEnvironment(instance, reoptimize=make_timed_policy(policy, per_event_cpu),
                                    seed=seed)
        report = sim.run()
        result = {
            "valid": report["valid"],
            "reason": None if report["valid"] else "physical constraint violated",
            "distance": report["distance"],
            "unserved": report["unserved"],
            "swaps": report["swaps"],
            "served": report["served"],
            "battery_violations": report["battery_violations"],
            "payload_violations": report["payload_violations"],
            "range_violations": report["range_violations"],
            "makespan": report["makespan"],
        }
    except EventTimeout as exc:
        result["reason"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - any submission crash invalidates the solution
        result["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm)

    result["runtime_s"] = time.perf_counter() - started
    return result


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------
def run(
    input_dir: Path,
    output_dir: Path,
    submission_dir: Path,
    per_event_cpu: float = 2.0,
    total_wall: float = 120.0,
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
    predictions: dict[str, dict] = {}

    for index, instance_path in enumerate(instances):
        instance = Instance.load(instance_path)
        name = instance.name
        try:
            policy = build_policy(module, instance, seed=index)
        except Exception as exc:  # noqa: BLE001
            predictions[name] = {"valid": False, "reason": f"policy error: {exc}",
                                 "distance": 0.0, "unserved": len(instance.orders), "swaps": 0,
                                 "served": 0, "battery_violations": 0, "payload_violations": 0,
                                 "range_violations": 0, "makespan": 0.0, "runtime_s": 0.0}
            print(f"  - {name}: POLICY ERROR ({exc})")
            continue

        result = run_instance(instance, policy, per_event_cpu, total_wall, seed=index)
        predictions[name] = result
        print(f"  - {name}: valid={result['valid']} served={result['served']} "
              f"distance={result['distance']:.1f} swaps={result['swaps']} "
              f"({result['runtime_s']:.2f}s)"
              + (f"  [{result['reason']}]" if result["reason"] else ""))

    (output_dir / "predictions.json").write_text(
        json.dumps({"instances": predictions}, indent=2), encoding="utf-8"
    )
    print(f"Wrote {output_dir / 'predictions.json'}")
    return predictions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codabench ingestion program (DDRP).")
    parser.add_argument("input_dir", nargs="?", type=Path, default=Path("/app/input"))
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("/app/output"))
    parser.add_argument("submission_dir", nargs="?", type=Path, default=Path("/app/submission"))
    parser.add_argument("--per-event-cpu", type=float, default=2.0,
                        help="CPU seconds allowed per re-optimisation")
    parser.add_argument("--total-wall", type=float, default=120.0,
                        help="wall-clock seconds allowed per workday")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run(args.input_dir, args.output_dir, args.submission_dir,
        per_event_cpu=args.per_event_cpu, total_wall=args.total_wall)


if __name__ == "__main__":
    main()
