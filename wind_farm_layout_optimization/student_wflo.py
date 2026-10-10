"""Student API for the WFLO assignment.

Write **one** solver by subclassing :class:`BaseWFLOSolver` and implementing
``solve``::

    from wind_farm_layout_optimization.student_wflo import BaseWFLOSolver

    class MySolver(BaseWFLOSolver):
        name = "my_solver"

        def solve(self, time_limit=None):
            layout = self.env.random_layout(seed=self.seed)
            ...  # your trajectory-based metaheuristic
            return layout          # a list of N [x, y] turbine positions

Your solver is executed as a script with the common command-line contract::

    python <your_solver>.py --instance <instance.json> --out <layout.json> --seed <int>

and must write a JSON object containing at least a ``"layout"`` key. The
helper :func:`run_solver_script` (used by the GUI and the autograder) runs a
solver script in a subprocess under a **strict CPU timeout**.

This module also ships a deliberately weak :class:`GridSolver` baseline, so you
always have something to compare against.
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

from wind_farm_layout_optimization.simulator_wflo import (
    WindFarmEnvironment,
    polygon_bounds,
)

ROOT = Path(__file__).resolve().parent.parent  # repository root


# =============================================================================
# Solver interface
# =============================================================================
class BaseWFLOSolver(ABC):
    """Base class for every WFLO solver.

    Subclasses must set :attr:`name` and implement :meth:`solve`. The
    environment (``self.env``) is the *only* way to evaluate a layout; never
    re-implement the physics.
    """

    name = "base"

    def __init__(self, env: WindFarmEnvironment, seed: int = 0) -> None:
        self.env = env
        self.instance = env.instance
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.history: list[float] = []  # optional: best objective per iteration

    @abstractmethod
    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        """Return a layout: a list of ``N`` ``[x, y]`` turbine positions."""
        raise NotImplementedError

    # -- convenience --------------------------------------------------------
    def score(self, layout: list[list[float]]) -> float:
        """Expected power (MW) of a layout --- the quantity to maximise."""
        return self.env.evaluate(layout)["expected_power_mw"]

    def record(self, value: float) -> None:
        """Append the best-so-far objective to the convergence history."""
        best = value if not self.history else max(self.history[-1], value)
        self.history.append(best)


class GridSolver(BaseWFLOSolver):
    """Dummy baseline: place turbines on a regular, staggered grid.

    The grid spacing equals the minimum spacing, so every pair of turbines is
    separated by construction --- no overlapping turbines, no physics needed.
    It is intentionally simple: beat it with your metaheuristic.
    """

    name = "grid"

    def solve(self, time_limit: float | None = None) -> list[list[float]]:
        inst = self.instance
        x0, y0, x1, y1 = polygon_bounds(inst.terrain)
        step = inst.min_spacing

        candidates: list[list[float]] = []
        n_rows = int((y1 - y0) // step) + 1
        n_cols = int((x1 - x0) // step) + 1
        for row in range(n_rows):
            row_offset = step / 2.0 if row % 2 else 0.0  # stagger alternate rows
            y = y0 + step / 2.0 + row * step
            for col in range(n_cols):
                x = x0 + step / 2.0 + col * step + row_offset
                if self.env.inside_terrain(x, y) and not self.env.inside_exclusion(x, y):
                    candidates.append([float(x), float(y)])

        # Pick N candidates spread evenly across the (row-major) candidate list.
        if len(candidates) >= inst.n_turbines:
            idx = np.linspace(0, len(candidates) - 1, inst.n_turbines).astype(int)
            layout = [candidates[i] for i in dict.fromkeys(int(i) for i in idx)]
        else:  # best effort: not enough room at the required spacing
            layout = candidates

        return layout


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
    run_cli(GridSolver)
