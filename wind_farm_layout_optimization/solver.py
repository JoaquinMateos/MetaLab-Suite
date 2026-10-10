"""Baseline trajectory solver for the WFLO problem — a stochastic hill climber.

This is the *reference* algorithm every other metaheuristic in this folder
will be compared against. It is a single-solution (trajectory) method:

1. start from a random feasible layout (via ``random_layout``);
2. repeatedly perturb **one** turbine (Gaussian move), and
3. accept the move when it improves the expected annual energy production.

Because it is a strict hill climber it gets stuck in local optima, which is
exactly the teaching point: swap it for simulated annealing, tabu search or a
population method and watch the convergence curve change.

Run it with (from the repository root)::

    uv run python -m wind_farm_layout_optimization.solver \
        --instance wind_farm_layout_optimization/instances/demo.json --iterations 3000
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from metalab import ConvergenceTrace
from wind_farm_layout_optimization.model import (
    Instance,
    count_violations,
    evaluate,
    random_layout,
)

DEFAULT_SOLUTIONS_DIR = Path(__file__).resolve().parent / "solutions"


@dataclass
class Solution:
    """A layout plus its evaluated objective value."""

    positions: np.ndarray
    objective: float  # aep_gwh, to be maximised
    diagnostics: dict = field(default_factory=dict)
    trace: ConvergenceTrace | None = None

    def to_dict(self, instance: Instance) -> dict:
        return {
            "instance": instance.name,
            "objective": self.objective,
            "positions": self.positions.tolist(),
            "diagnostics": self.diagnostics,
            "history": self.trace.best_increments if self.trace else [],
        }

    def save(self, path: str | Path, instance: Instance) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(instance), indent=2), encoding="utf-8")
        return path


class HillClimbingSolver:
    """Stochastic hill climbing with Gaussian moves."""

    def __init__(self, instance: Instance, seed: int | None = None) -> None:
        self.instance = instance
        self.rng = np.random.default_rng(instance.seed if seed is None else seed)

    # -- feasibility helpers ------------------------------------------------
    def _is_feasible(self, positions: np.ndarray, moved: int) -> bool:
        margin = self.instance.rotor_radius
        if not np.all((positions >= margin) & (positions <= self.instance.side - margin)):
            return False
        min_d = self.instance.min_spacing
        for j in range(len(positions)):
            if j == moved:
                continue
            if np.linalg.norm(positions[moved] - positions[j]) < min_d - 1e-9:
                return False
        return True

    def solve(self, iterations: int = 3000, initial_step: float = 150.0) -> Solution:
        """Run the climber and return the best layout found."""
        instance = self.instance
        current = random_layout(instance, self.rng)
        current_obj = evaluate(instance, current)["aep_gwh"]

        trace = ConvergenceTrace("Hill Climbing", maximize=True)
        trace.update(current_obj, 0)

        best, best_obj = current.copy(), current_obj
        n = instance.n_turbines
        step = initial_step

        for it in range(1, iterations + 1):
            # Cool the step size so late moves are fine-grained.
            step = initial_step * (1.0 - 0.9 * it / iterations)
            candidate = current.copy()
            moved = int(self.rng.integers(0, n))
            candidate[moved] += self.rng.normal(0.0, step, size=2)
            candidate[moved] = np.clip(candidate[moved], 0.0, instance.side)

            if not self._is_feasible(candidate, moved):
                trace.update(best_obj, it)
                continue

            cand_obj = evaluate(instance, candidate)["aep_gwh"]
            if cand_obj > current_obj:  # strictly better -> accept (hill climb)
                current, current_obj = candidate, cand_obj
                if cand_obj > best_obj:
                    best, best_obj = candidate.copy(), cand_obj
            trace.update(best_obj, it)

        diagnostics = evaluate(instance, best)
        diagnostics["spacing_violations"] = count_violations(instance, best)
        return Solution(positions=best, objective=best_obj, diagnostics=diagnostics, trace=trace)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseline hill-climbing solver for WFLO.")
    parser.add_argument("--instance", type=Path, required=True, help="path to an instance JSON")
    parser.add_argument("--iterations", type=int, default=3000, help="number of iterations")
    parser.add_argument("--step", type=float, default=150.0, help="initial move size in metres")
    parser.add_argument("--seed", type=int, default=None, help="override the instance seed")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write the solution JSON "
        "(default: wind_farm_layout_optimization/solutions/<instance>.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Solution:
    args = parse_args(argv)
    instance = Instance.load(args.instance)
    solver = HillClimbingSolver(instance, seed=args.seed)
    solution = solver.solve(iterations=args.iterations, initial_step=args.step)

    out = args.out or (DEFAULT_SOLUTIONS_DIR / f"{instance.name}.json")
    solution.save(out, instance)

    print(f"Instance : {instance.name} ({instance.n_turbines} turbines)")
    print(f"AEP      : {solution.objective:,.1f} GWh/yr")
    print(f"Capacity : {solution.diagnostics.get('capacity_factor', 0) * 100:.1f} %")
    print(f"Solution : {out}")
    return solution


if __name__ == "__main__":
    main()
