"""Baseline solver for the DDRP — cheapest-insertion construction.

This reference algorithm builds a plan greedily and is the yardstick every
trajectory-based metaheuristic in this folder will be compared against:

* process requests in order of release time (respecting the *dynamic* nature
  of the problem);
* for each request, try every feasible insertion of its pickup/drop-off pair
  into every vehicle route;
* keep the insertion that increases total travel distance the least;
* if no feasible insertion exists, the request is left unserved.

Greedy construction is fast and gives a respectable starting point, but it is
myopic — a great candidate to be improved by local search or annealing.

Run it with (from the repository root)::

    uv run python -m dynamic_dial_a_ride.solver \
        --instance dynamic_dial_a_ride/instances/demo.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from dynamic_dial_a_ride.model import (
    Instance,
    evaluate,
    route_is_feasible,
    route_travel_distance,
)
from metalab import ConvergenceTrace

DEFAULT_SOLUTIONS_DIR = Path(__file__).resolve().parent / "solutions"

Stop = tuple[int, str]


@dataclass
class Solution:
    """A plan (one route per vehicle) plus its evaluated objective value."""

    routes: list[list[Stop]]
    cost: float  # to be minimised
    diagnostics: dict = field(default_factory=dict)
    trace: ConvergenceTrace | None = None

    def to_dict(self, instance: Instance) -> dict:
        return {
            "instance": instance.name,
            "cost": self.cost,
            "routes": [[list(stop) for stop in route] for route in self.routes],
            "diagnostics": self.diagnostics,
            "history": self.trace.best_increments if self.trace else [],
        }

    def save(self, path: str | Path, instance: Instance) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(instance), indent=2), encoding="utf-8")
        return path


class CheapestInsertionSolver:
    """Greedy cheapest-insertion heuristic for the DDRP."""

    def __init__(self, instance: Instance) -> None:
        self.instance = instance

    def _best_insertion(
        self, route: list[Stop], request_id: int
    ) -> tuple[float, list[Stop]] | None:
        """Return the (distance delta, new route) of the best feasible insertion."""
        base = route_travel_distance(self.instance, route)
        best: tuple[float, list[Stop]] | None = None
        length = len(route)
        for i in range(length + 1):  # pickup position
            for j in range(i, length + 1):  # drop-off position (>= pickup)
                candidate = (
                    route[:i]
                    + [(request_id, "P")]
                    + route[i:j]
                    + [(request_id, "D")]
                    + route[j:]
                )
                if not route_is_feasible(self.instance, candidate):
                    continue
                delta = route_travel_distance(self.instance, candidate) - base
                if best is None or delta < best[0]:
                    best = (delta, candidate)
        return best

    def solve(self) -> Solution:
        """Build the plan request by request, in order of release time."""
        instance = self.instance
        routes: list[list[Stop]] = [[] for _ in range(instance.n_vehicles)]
        ordered = sorted(instance.requests, key=lambda r: r.release_time)

        trace = ConvergenceTrace("Cheapest Insertion", maximize=False)
        trace.update(evaluate(instance, routes)["cost"], 0)

        for step, request in enumerate(ordered, start=1):
            best: tuple[float, int, list[Stop]] | None = None
            for vehicle, route in enumerate(routes):
                insertion = self._best_insertion(route, request.id)
                if insertion is None:
                    continue
                delta, candidate = insertion
                if best is None or delta < best[0]:
                    best = (delta, vehicle, candidate)
            if best is not None:
                routes[best[1]] = best[2]
            trace.update(evaluate(instance, routes)["cost"], step)

        diagnostics = evaluate(instance, routes)
        return Solution(
            routes=routes, cost=diagnostics["cost"], diagnostics=diagnostics, trace=trace
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cheapest-insertion baseline for the DDRP.")
    parser.add_argument("--instance", type=Path, required=True, help="path to an instance JSON")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write the solution JSON "
        "(default: dynamic_dial_a_ride/solutions/<instance>.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> Solution:
    args = parse_args(argv)
    instance = Instance.load(args.instance)
    solution = CheapestInsertionSolver(instance).solve()

    out = args.out or (DEFAULT_SOLUTIONS_DIR / f"{instance.name}.json")
    solution.save(out, instance)

    print(f"Instance : {instance.name} ({len(instance.requests)} requests)")
    print(f"Served   : {solution.diagnostics['served']} / {len(instance.requests)}")
    print(f"Distance : {solution.diagnostics['total_distance']:.1f}")
    print(f"Cost     : {solution.cost:.1f}")
    print(f"Solution : {out}")
    return solution


if __name__ == "__main__":
    main()
