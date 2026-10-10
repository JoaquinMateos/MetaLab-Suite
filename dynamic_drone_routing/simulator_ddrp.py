"""SimPy discrete-event simulation engine for the Dynamic Drone Routing Problem.

This is the *given* part of the DDRP assignment: a simulator that executes a
dispatch plan against a stream of orders that arrive over a working day.

Model
-----
* A single **depot** and a fleet of **drones**. Each drone has a payload
  capacity ``Q`` and a battery whose usable energy is expressed as a maximum
  flight distance (``max_range``).
* Drones fly **line of sight** (straight Euclidean legs) at a constant speed and
  spend a fixed ``service_time`` hovering/landing at every stop.
* A drone leaves the depot with a load, serves a sequence of customers, and
  returns to the depot, where its battery is **swapped instantly**.
* **Static** orders (``release_time == 0``) are known at the start of the day;
  **dynamic** orders become known at their ``release_time > 0``. Whenever a
  dynamic order arrives the simulation **pauses** (the clock is frozen), calls
  :meth:`SimulationEnvironment.reoptimize`, and resumes.

The dispatch policy is pluggable: pass your own ``reoptimize`` callable with the
signature ``reoptimize(state: ReoptState) -> dict[int, list[int]]`` mapping a
drone id to an ordered list of order ids. A simple greedy planner is provided so
the simulator runs out of the box.

Run the demo with (from the repository root)::

    uv run python -m dynamic_drone_routing.simulator_ddrp \
        --instance dynamic_drone_routing/instances/toy.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import simpy

UNSERVED_PENALTY = 1000.0  # objective penalty per order left unserved
DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"


# =============================================================================
# Data model
# =============================================================================
@dataclass
class Order:
    """A single delivery: drop ``weight`` kg at ``(x, y)``."""

    id: int
    x: float
    y: float
    weight: float
    release_time: float = 0.0
    static: bool = True

    @property
    def position(self) -> tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_dict(cls, data: dict) -> Order:
        return cls(**data)


@dataclass
class Fleet:
    """Fleet-wide drone specifications."""

    n_drones: int = 3
    capacity: float = 3.0  # max payload Q (kg)
    max_range: float = 40.0  # max flight distance per battery (distance units)
    speed: float = 1.0  # distance units per minute
    service_time: float = 1.0  # minutes spent at each stop

    @classmethod
    def from_dict(cls, data: dict) -> Fleet:
        return cls(**data)


@dataclass
class Instance:
    """A full workday: depot, fleet, orders and horizon."""

    name: str
    depot: tuple[float, float]
    fleet: Fleet
    workday: float
    orders: list[Order] = field(default_factory=list)
    seed: int = 0

    @property
    def static_orders(self) -> list[Order]:
        return [o for o in self.orders if o.release_time <= 0.0]

    @property
    def dynamic_orders(self) -> list[Order]:
        return [o for o in self.orders if o.release_time > 0.0]

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Instance:
        data = dict(data)
        data["depot"] = tuple(data["depot"])
        data["fleet"] = Fleet.from_dict(data["fleet"])
        data["orders"] = [Order.from_dict(o) for o in data.get("orders", [])]
        return cls(**data)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Instance:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class ReoptState:
    """Everything a dispatch policy may look at when it is re-optimising."""

    now: float
    pending_orders: list[Order]
    idle_drones: list[Drone]
    instance: Instance


# =============================================================================
# Drone
# =============================================================================
class Drone:
    """A single drone process: it waits when idle, flies when dispatched."""

    def __init__(self, env: simpy.Environment, sim: SimulationEnvironment, drone_id: int) -> None:
        self.env = env
        self.sim = sim
        self.id = drone_id
        self.spec = sim.instance.fleet
        self.position: tuple[float, float] = sim.instance.depot
        self.payload = 0.0
        self.battery = self.spec.max_range
        self.routes: list[list[int]] = []  # queue of assigned routes
        self.busy = False
        self._idle_event: simpy.Event | None = None
        self.process = env.process(self._run())

    @property
    def is_idle(self) -> bool:
        """A drone is idle when it is parked at the depot with nothing queued."""
        return not self.routes and not self.busy

    def assign(self, route: list[int]) -> None:
        """Queue a route and wake the drone if it is currently waiting."""
        self.routes.append(route)
        if self._idle_event is not None and not self._idle_event.triggered:
            self._idle_event.succeed()

    # -- process ------------------------------------------------------------
    def _run(self):
        while True:
            while not self.routes:  # wait until dispatched
                self._idle_event = self.env.event()
                yield self._idle_event
            route = self.routes.pop(0)
            yield from self._fly(route)

    def _fly(self, route: list[int]):
        """Fly the route (line of sight), deliver, then return and swap battery."""
        self.busy = True
        for order_id in route:
            order = self.sim.orders_by_id[order_id]
            yield from self._travel(order.position)
            self.payload -= order.weight
            yield self.env.timeout(self.spec.service_time)  # hover / drop
            self.sim._deliver(order)
        yield from self._travel(self.sim.instance.depot)
        self.battery = self.spec.max_range  # instant battery swap
        self.sim.battery_swaps += 1
        self.sim._log("battery_swap", drone=self.id)
        self.busy = False

    def _travel(self, target: tuple[float, float]):
        leg = math.dist(self.position, target)
        yield self.env.timeout(leg / self.spec.speed)
        self.sim.total_distance += leg
        self.battery -= leg
        self.position = target


# =============================================================================
# Dispatch policy (default: nearest-feasible greedy)
# =============================================================================
def greedy_planner(state: ReoptState) -> dict[int, list[int]]:
    """Assign each idle drone a route of nearby feasible orders.

    Feasibility: the round-trip distance must not exceed the drone range and the
    total payload must not exceed the capacity. This is the baseline a student
    is expected to beat.
    """
    remaining = {o.id: o for o in state.pending_orders}
    depot = state.instance.depot
    plan: dict[int, list[int]] = {}

    for drone in state.idle_drones:
        route: list[int] = []
        load = 0.0
        travelled = 0.0
        current = depot
        while True:
            best: tuple[float, int, Order] | None = None
            for order in remaining.values():
                if load + order.weight > drone.spec.capacity:
                    continue
                leg = math.dist(current, order.position)
                if travelled + leg + math.dist(order.position, depot) > drone.spec.max_range:
                    continue  # could not get back to the depot
                if best is None or leg < best[0]:
                    best = (leg, order.id, order)
            if best is None:
                break
            leg, order_id, order = best
            route.append(order_id)
            travelled += leg
            current = order.position
            load += order.weight
            del remaining[order_id]
        if route:
            plan[drone.id] = route
    return plan


# =============================================================================
# Simulation environment
# =============================================================================
class SimulationEnvironment:
    """SimPy engine that runs a dispatch policy over a workday."""

    def __init__(
        self,
        instance: Instance,
        reoptimize: Callable[[ReoptState], dict[int, list[int]]] | None = None,
        seed: int = 0,
    ) -> None:
        self.instance = instance
        self.seed = seed
        self.reoptimize_fn = reoptimize or greedy_planner

        self.env = simpy.Environment()
        self.orders_by_id = {o.id: o for o in instance.orders}
        self.drones = [Drone(self.env, self, i) for i in range(instance.fleet.n_drones)]

        # bookkeeping
        self.released: set[int] = set()
        self.planned: set[int] = set()
        self.delivered: dict[int, float] = {}
        self.total_distance = 0.0
        self.battery_swaps = 0
        self.reoptimizations = 0
        self.is_paused = False
        self.events: list[dict] = []

        self._dynamic = sorted(
            instance.dynamic_orders, key=lambda order: order.release_time
        )

    # -- helpers ------------------------------------------------------------
    def _log(self, kind: str, **details) -> None:
        self.events.append({"t": round(self.env.now, 3), "event": kind, **details})

    def pending_orders(self) -> list[Order]:
        """Released orders that are neither delivered nor currently planned."""
        return [
            order
            for order in self.orders_by_id.values()
            if order.id in self.released
            and order.id not in self.planned
            and order.id not in self.delivered
        ]

    def _deliver(self, order: Order) -> None:
        self.delivered[order.id] = self.env.now
        self.planned.discard(order.id)
        self._log("delivery", order=order.id)

    # -- the re-optimisation hook ------------------------------------------
    def reoptimize(self) -> None:
        """Pause the clock, ask the policy for a plan, and apply it.

        The callable runs *synchronously* inside the current event, so SimPy time
        does not advance while it works: the simulation is effectively paused.
        """
        self.reoptimizations += 1
        self.is_paused = True
        self._log("pause")

        state = ReoptState(
            now=self.env.now,
            pending_orders=self.pending_orders(),
            idle_drones=[drone for drone in self.drones if drone.is_idle],
            instance=self.instance,
        )
        plan = self.reoptimize_fn(state) or {}
        for drone_id, route in plan.items():
            feasible = [
                order_id
                for order_id in route
                if order_id in self.released
                and order_id not in self.planned
                and order_id not in self.delivered
            ]
            if feasible:
                self.drones[drone_id].assign(feasible)
                self.planned.update(feasible)
                self._log("dispatch", drone=drone_id, route=feasible)

        self.is_paused = False
        self._log("resume")

    # -- processes ----------------------------------------------------------
    def _dynamic_order_process(self):
        """Release dynamic orders one by one, re-optimising at each arrival."""
        for order in self._dynamic:
            yield self.env.timeout(order.release_time - self.env.now)
            self.released.add(order.id)
            self._log("order_arrival", order=order.id, weight=order.weight)
            self.reoptimize()

    # -- run ----------------------------------------------------------------
    def run(self) -> dict:
        """Execute the workday and return the performance report."""
        for order in self.instance.static_orders:
            self.released.add(order.id)
        self._log("workday_start", static_orders=len(self.instance.static_orders))

        self.reoptimize()  # initial plan for the static orders
        self.env.process(self._dynamic_order_process())
        self.env.run(until=self.instance.workday)

        return self.report()

    def report(self) -> dict:
        served = len(self.delivered)
        total = len(self.orders_by_id)
        unserved = total - served
        makespan = max(self.delivered.values()) if self.delivered else 0.0
        return {
            "instance": self.instance.name,
            "served": served,
            "unserved": unserved,
            "total_orders": total,
            "total_distance": self.total_distance,
            "battery_swaps": self.battery_swaps,
            "reoptimizations": self.reoptimizations,
            "makespan": makespan,
            "objective": self.total_distance + UNSERVED_PENALTY * unserved,
            "deliveries": dict(sorted(self.delivered.items())),
        }


# =============================================================================
# CLI demo
# =============================================================================
def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Run the DDRP SimPy simulator (greedy baseline).")
    parser.add_argument(
        "--instance", type=Path, default=DEFAULT_INSTANCES_DIR / "toy.json",
        help="workday JSON produced by generate_instances_ddrp.py",
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    args = parser.parse_args(argv)

    instance = Instance.load(args.instance)
    sim = SimulationEnvironment(instance, seed=args.seed)
    result = sim.run()

    print(f"Instance        : {instance.name} ({result['total_orders']} orders, "
          f"{instance.fleet.n_drones} drones)")
    print(f"Served          : {result['served']} / {result['total_orders']}")
    print(f"Total distance  : {result['total_distance']:.1f}")
    print(f"Battery swaps   : {result['battery_swaps']}")
    print(f"Re-optimisations: {result['reoptimizations']}")
    print(f"Makespan        : {result['makespan']:.1f} min")
    print(f"Objective       : {result['objective']:.1f} (distance + penalty x unserved)")
    return result


if __name__ == "__main__":
    main()
