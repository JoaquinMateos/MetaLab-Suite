"""Student API and **skeleton** for the DDRP assignment.

This file is the starting point for **your** dispatch policy. It contains

* :class:`BaseSolver` --- the abstract interface every policy must respect;
* :class:`MySolver` --- an empty skeleton you fill in (search for ``TODO``);
* the shared command-line contract used by the GUI and the autograder.

Object-oriented recipe
----------------------
1. Create a subclass of :class:`BaseSolver`.
2. Implement :meth:`reoptimize`. The engine calls it at ``t = 0`` and at every
   dynamic arrival; return ``{drone_id: [order_id, ...]}`` for the idle drones.
3. Respect the payload capacity and the battery range **for the whole round
   trip** (depot → stops → depot); otherwise the autograder invalidates you.

Run your policy with (from the repository root)::

    uv run python -m dynamic_drone_routing.student_ddrp \
        --instance dynamic_drone_routing/instances/toy.json \
        --out dynamic_drone_routing/solutions/toy_mysolver.json

The only complete algorithm you are given is the random search in
``random_search_ddrp.py``.
"""

from __future__ import annotations

import argparse
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from dynamic_drone_routing.given.simulator_ddrp import (
    Instance,
    ReoptState,
    SimulationEnvironment,
)

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"
DEFAULT_SOLUTIONS_DIR = Path(__file__).resolve().parent / "solutions"


# =============================================================================
# The interface --- implement this
# =============================================================================
class BaseSolver(ABC):
    """Abstract base class for every DDRP dispatch policy.

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


class MySolver(BaseSolver):
    """Skeleton for **your** dispatch policy --- fill in :meth:`reoptimize`.

    Replace the ``raise`` with your algorithm. Some design questions:

    * how do you choose which orders to serve for each idle drone (nearest
      neighbour, insertion, clustering, look-ahead)?
    * how do you decide the order **within** a route?
    * how do you react when a dynamic order arrives mid-route?

    Remember the hard constraints: total payload <= ``state.instance.fleet.capacity``
    and the whole round trip <= ``state.instance.fleet.max_range``.
    """

    name = "my_solver"

    def reoptimize(self, state: ReoptState) -> dict[int, list[int]]:
        # TODO 1 --- look at state.pending_orders and state.idle_drones.
        # TODO 2 --- build a route per idle drone, checking, for every candidate
        #            order, the payload capacity and the round-trip battery.
        # TODO 3 --- return {drone.id: [order_id, ...]} (only non-empty routes).
        raise NotImplementedError("Implement MySolver.reoptimize() --- see the TODO notes.")


def build_policy(instance: Instance, seed: int = 0) -> Callable[[ReoptState], dict[int, list[int]]]:
    """Return a dispatch policy callable (override this in your own module)."""
    return MySolver(instance, seed=seed).reoptimize


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
    try:
        run_cli(MySolver)
    except NotImplementedError as exc:
        print(f"[skeleton] {exc}")
        print("[skeleton] Open student_ddrp.py, implement MySolver.reoptimize(), then run again.")
