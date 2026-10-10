"""Student API for the DDRP assignment.

Write **one** dispatch policy by subclassing :class:`BaseSolver` and implementing
``reoptimize``::

    from dynamic_drone_routing.student_ddrp import BaseSolver

    class MySolver(BaseSolver):
        name = "my_solver"

        def reoptimize(self, state):
            # state.pending_orders, state.idle_drones, state.instance, state.now
            return {drone.id: [order_id, ...]}   # one ordered route per idle drone

The simulator calls your policy at ``t = 0`` and again at every dynamic order
arrival. A route must respect **both** the payload capacity and the battery
range **for the whole round trip** (depot → stops → depot); otherwise the
autograder invalidates the solution.

A :class:`GreedySolver` (nearest neighbour with strict round-trip checks) is
provided as a baseline you must beat.

Run it with (from the repository root)::

    uv run python -m dynamic_drone_routing.student_ddrp \
        --instance dynamic_drone_routing/instances/toy.json \
        --out dynamic_drone_routing/solutions/toy_greedy.json
"""

from __future__ import annotations

import argparse
import json
import math
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from dynamic_drone_routing.simulator_ddrp import (
    Instance,
    ReoptState,
    SimulationEnvironment,
)

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"
DEFAULT_SOLUTIONS_DIR = Path(__file__).resolve().parent / "solutions"


# =============================================================================
# Solver interface
# =============================================================================
class BaseSolver(ABC):
    """Base class for every DDRP dispatch policy.

    ``self.instance`` is available for look-ahead; the *only* thing the engine
    asks of you is :meth:`reoptimize`.
    """

    name = "base"

    def __init__(self, instance: Instance, seed: int = 0) -> None:
        self.instance = instance
        self.seed = seed

    @abstractmethod
    def reoptimize(self, state: ReoptState) -> dict[int, list[int]]:
        """Return ``{drone_id: [order_id, ...]}`` for the currently idle drones."""
        raise NotImplementedError


class GreedySolver(BaseSolver):
    """Nearest-neighbour baseline with strict battery and payload checks.

    For each idle drone it repeatedly appends the closest still-unassigned order
    that keeps the **whole round trip** (depot → stops → depot) within the
    battery range and the **total payload** within capacity. It is myopic ---
    improve it (look-ahead, clustering, re-routing, restarts).
    """

    name = "greedy"

    def reoptimize(self, state: ReoptState) -> dict[int, list[int]]:
        depot = state.instance.depot
        capacity = state.instance.fleet.capacity
        max_range = state.instance.fleet.max_range

        remaining = {order.id: order for order in state.pending_orders}
        plan: dict[int, list[int]] = {}

        for drone in state.idle_drones:
            route: list[int] = []
            load = 0.0  # payload currently on board (kg)
            travelled = 0.0  # distance covered so far in this route
            current = depot

            while True:
                best: tuple[float, int] | None = None
                for order in remaining.values():
                    if load + order.weight > capacity + 1e-9:
                        continue  # payload limit
                    leg = math.dist(current, order.position)
                    # Strict round-trip battery check: after serving this order
                    # the drone must still be able to return to the depot.
                    if travelled + leg + math.dist(order.position, depot) > max_range + 1e-9:
                        continue
                    if best is None or leg < best[0]:
                        best = (leg, order.id)
                if best is None:
                    break
                leg, order_id = best
                route.append(order_id)
                travelled += leg
                current = remaining[order_id].position
                load += remaining[order_id].weight
                del remaining[order_id]

            if route:
                plan[drone.id] = route

        return plan


def build_policy(instance: Instance, seed: int = 0) -> Callable[[ReoptState], dict[int, list[int]]]:
    """Return a dispatch policy callable (override this in your own module)."""
    return GreedySolver(instance, seed=seed).reoptimize


# =============================================================================
# Shared command-line contract
# =============================================================================
def build_arg_parser(description: str = "DDRP solver") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--instance", type=Path, required=True, help="workday JSON")
    parser.add_argument("--out", type=Path, required=True, help="where to write the run JSON")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--time-limit", type=float, default=None, help="soft wall budget (s)")
    return parser


def run_cli(solver_cls: type[BaseSolver], argv: list[str] | None = None) -> dict:
    """Run ``solver_cls`` from the command line and write the full run JSON."""
    args = build_arg_parser(f"{solver_cls.__name__} --- DDRP policy").parse_args(argv)
    instance = Instance.load(args.instance)
    solver = solver_cls(instance, seed=args.seed)

    started = time.perf_counter()
    sim = SimulationEnvironment(instance, reoptimize=solver.reoptimize, seed=args.seed)
    report = sim.run()
    runtime = time.perf_counter() - started

    result = {"solver": solver.name, "runtime_s": runtime, **sim.export()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"[{solver.name}] served={report['served']}/{report['total_orders']} "
        f"distance={report['distance']:.1f} swaps={report['swaps']} "
        f"valid={report['valid']} ({runtime:.2f}s)"
    )
    return result


if __name__ == "__main__":
    run_cli(GreedySolver)
