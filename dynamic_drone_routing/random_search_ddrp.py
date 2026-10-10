"""The only algorithm you are given: a random-search dispatch policy (OOP example).

For each re-optimisation it shuffles the pending orders and the idle drones and
greedily appends each order to the first drone whose **round trip** still fits
the battery range and whose **payload** stays within capacity. Reading it shows
you how to subclass :class:`BaseSolver` and respect the constraints; improving on
it is your task (see ``student_ddrp.py``).

Run it with (from the repository root)::

    uv run python -m dynamic_drone_routing.random_search_ddrp \
        --instance dynamic_drone_routing/instances/toy.json \
        --out dynamic_drone_routing/solutions/toy_random.json
"""

from __future__ import annotations

import math

import numpy as np

from dynamic_drone_routing.given.simulator_ddrp import ReoptState
from dynamic_drone_routing.student_ddrp import BaseSolver, run_cli


class RandomSearchPolicy(BaseSolver):
    """Randomized construction: shuffle orders and drones, then fill routes."""

    name = "random_search"

    def __init__(self, instance, seed: int = 0) -> None:
        super().__init__(instance, seed)
        self.rng = np.random.default_rng(seed)

    def reoptimize(self, state: ReoptState) -> dict[int, list[int]]:
        fleet = state.instance.fleet
        depot = state.instance.depot

        pending = list(state.pending_orders)
        self.rng.shuffle(pending)  # random order of insertion
        idle = [drone.id for drone in state.idle_drones]
        self.rng.shuffle(idle)  # random preference between drones

        routes: dict[int, list[int]] = {drone_id: [] for drone_id in idle}
        load = dict.fromkeys(idle, 0.0)
        travelled = dict.fromkeys(idle, 0.0)
        position = {drone_id: depot for drone_id in idle}

        for order in pending:
            for drone_id in idle:
                if load[drone_id] + order.weight > fleet.capacity + 1e-9:
                    continue  # payload limit
                leg = math.dist(position[drone_id], order.position)
                home = math.dist(order.position, depot)
                if travelled[drone_id] + leg + home > fleet.max_range + 1e-9:
                    continue  # cannot get home on one battery
                routes[drone_id].append(order.id)
                load[drone_id] += order.weight
                travelled[drone_id] += leg
                position[drone_id] = order.position
                break

        return {drone_id: route for drone_id, route in routes.items() if route}


if __name__ == "__main__":
    run_cli(RandomSearchPolicy)
