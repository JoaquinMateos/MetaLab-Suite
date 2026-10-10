"""Student API and **skeleton** for the WFLO assignment.

This file is the starting point for **your** metaheuristic. It contains

* :class:`BaseWFLOSolver` --- the abstract interface every solver must respect;
* :class:`MySolver` --- an empty skeleton you fill in (search for ``TODO``);
* the shared command-line contract and the subprocess runner used by the GUI and
  the autograder.

Object-oriented recipe
----------------------
1. Create a subclass of :class:`BaseWFLOSolver`.
2. Implement :meth:`solve` by walking **one** solution through the search space:
   generate an initial layout, perturb it repeatedly, keep the best one, and
   call :meth:`record` so the convergence curve can be plotted.
3. Score any candidate with :meth:`score` (never re-implement the physics).

Run your solver with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.student_wflo \
        --instance wind_farm_layout_optimization/instances/toy.json \
        --out wind_farm_layout_optimization/solutions/toy_mysolver.json

The only complete algorithm you are given is the random search in
``random_search_wflo.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from wind_farm_layout_optimization.given.simulator_wflo import WindFarmEnvironment

ROOT = Path(__file__).resolve().parent.parent  # repository root


# =============================================================================
# The interface --- implement this
# =============================================================================
class BaseWFLOSolver(ABC):
    """Abstract base class for every WFLO solver.

    A *trajectory-based* metaheuristic evolves a single incumbent layout. Use
    ``self.env`` to evaluate layouts and ``self.rng`` for reproducibility.
    """

    name = "base"

    def __init__(self, env: WindFarmEnvironment, seed: int = 0) -> None:
        self.env = env
        self.instance = env.instance
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.history: list[float] = []  # best-so-far objective per iteration

    @abstractmethod
    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        """Return a layout: a list of ``N`` ``[x, y]`` turbine positions."""
        raise NotImplementedError

    # -- helpers ------------------------------------------------------------
    def score(self, layout: list[list[float]]) -> float:
        """Expected power (MW) of a layout --- the quantity to maximise."""
        return self.env.evaluate(layout)["expected_power_mw"]

    def record(self, value: float) -> None:
        """Append the best-so-far objective to the convergence history."""
        best = value if not self.history else max(self.history[-1], value)
        self.history.append(best)


class MySolver(BaseWFLOSolver):
    """Skeleton for **your** metaheuristic --- fill in :meth:`solve`.

    Replace the ``raise`` with your algorithm. Some design questions to answer:

    * **Initial solution** --- random (``self.env.random_layout``) or greedy?
    * **Neighbourhood** --- which move produces a neighbouring layout?
    * **Acceptance rule** --- hill climbing (only improvements), simulated
      annealing (accept worsening moves with ``exp(-delta / T)``), tabu, ...?

    Every call to :meth:`record` adds a point to the convergence curve.
    """

    name = "my_solver"

    def __init__(self, env: WindFarmEnvironment, seed: int = 0, iterations: int = 5000) -> None:
        super().__init__(env, seed)
        self.iterations = iterations

    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        # TODO 1 --- initial solution (must be feasible).
        #     layout = self.env.random_layout(seed=self.seed)

        # TODO 2 --- walk a single solution through the search space.
        #     while budget remains:
        #         candidate = <perturb `layout`>
        #         value = self.score(candidate)
        #         <accept or reject>
        #         self.record(best_value)
        #     Hint: an infeasible candidate can be repaired or rejected. Check
        #     feasibility with self.env.is_feasible(candidate).

        # TODO 3 --- return the best feasible layout found.
        raise NotImplementedError("Implement MySolver.solve() --- see the TODO notes above.")


# =============================================================================
# Shared command-line contract
# =============================================================================
def build_arg_parser(description: str = "WFLO solver") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--instance", type=Path, required=True, help="instance JSON")
    parser.add_argument("--out", type=Path, required=True, help="where to write the layout JSON")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--time-limit", type=float, default=None, help="soft time budget (s)")
    return parser


def run_cli(solver_cls: type[BaseWFLOSolver], argv: list[str] | None = None) -> dict:
    """Run ``solver_cls`` from the command line and write the standard result JSON."""
    args = build_arg_parser(f"{solver_cls.__name__} --- WFLO solver").parse_args(argv)
    env = WindFarmEnvironment.from_file(args.instance)
    solver = solver_cls(env, seed=args.seed)

    started = time.perf_counter()
    layout = solver.solve(time_limit=args.time_limit)
    runtime = time.perf_counter() - started

    report = env.evaluate(layout)
    result = {
        "solver": solver.name,
        "instance": env.instance.name,
        "layout": layout,
        "objective": report["expected_power_mw"],
        "history": solver.history,
        "runtime_s": runtime,
        "report": report,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"[{solver.name}] power={report['expected_power_mw']:.3f} MW "
        f"efficiency={report['expected_efficiency'] * 100:.1f}% "
        f"feasible={report['feasible']} ({runtime:.2f}s)"
    )
    return result


# =============================================================================
# Subprocess runtime (strict CPU timeout) used by the GUI and the autograder
# =============================================================================
def _cpu_limiter(cpu_seconds: float):
    """Return a ``preexec_fn`` enforcing a hard CPU-time limit (POSIX)."""
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX platforms
        return None

    def _limit() -> None:  # pragma: no cover - runs in the child process
        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_seconds), int(cpu_seconds) + 1))

    return _limit


def run_solver_script(
    script: str | Path,
    instance: str | Path,
    out: str | Path,
    seed: int = 0,
    wall_limit: float = 60.0,
    cpu_limit: float = 60.0,
    cwd: str | Path = ROOT,
) -> dict:
    """Run a solver *script* in a subprocess with a strict CPU + wall timeout.

    Returns ``{"ok": bool, "result": dict | None, "error": str | None,
    "runtime_s": float}``. The solver must follow the command-line contract
    ``--instance --out --seed`` and write a JSON file with a ``layout`` key.
    """
    out = Path(out)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [
        sys.executable,
        str(Path(script).resolve()),
        "--instance",
        str(Path(instance).resolve()),
        "--out",
        str(out.resolve()),
        "--seed",
        str(seed),
    ]

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=wall_limit,
            preexec_fn=_cpu_limiter(cpu_limit),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "result": None,
            "error": f"timeout: exceeded the {wall_limit:g}s wall / {cpu_limit:g}s CPU limit",
            "runtime_s": time.perf_counter() - started,
        }

    runtime = time.perf_counter() - started
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        return {
            "ok": False,
            "result": None,
            "error": f"solver exited with code {proc.returncode}: " + " | ".join(tail),
            "runtime_s": runtime,
        }
    if not out.exists():
        return {"ok": False, "result": None, "error": "solver produced no output file",
                "runtime_s": runtime}
    return {"ok": True, "result": json.loads(out.read_text(encoding="utf-8")),
            "error": None, "runtime_s": runtime}


if __name__ == "__main__":
    try:
        run_cli(MySolver)
    except NotImplementedError as exc:
        print(f"[skeleton] {exc}")
        print("[skeleton] Open student_wflo.py, implement MySolver.solve(), then run again.")
