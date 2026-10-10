"""Reference model for the Dynamic Dial-a-Ride Problem (DDRP).

A dial-a-ride problem asks a fleet of capacitated vehicles to serve a set of
*transport requests*. Each request is a passenger who must be picked up at an
origin and dropped off at a destination. In the **dynamic** variant, requests
becomes known over time (they have a ``release_time``), so a dispatcher must
decide routes without knowing the future.

Reference formulation used here
-------------------------------
* Service area: the square ``[0, side] x [0, side]`` with a single ``depot``.
* Every request has an origin, a destination, a demand, a release time and an
  optional maximum ride time.
* Vehicles travel at constant ``speed``, spend ``service_time`` at each stop,
  and cannot exceed their ``capacity`` at any moment.
* A **plan** (solution) is a list of routes, one per vehicle. A route is a
  sequence of stops ``(request_id, "P" | "D")``.

Objective (minimised)
---------------------
``cost = total_distance + w_unserved * unserved + w_wait * total_wait + w_violation * violations``

The penalties are deliberately large so that a planner is strongly pushed to
serve every request while keeping total travel short.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Objective weights (tune these to change the problem's flavour).
UNSERVED_PENALTY = 1000.0  # per request left unserved
WAIT_WEIGHT = 0.5  # per unit of time a passenger waits before pickup
VIOLATION_PENALTY = 500.0  # per capacity/precedence violation


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Request:
    """A single transport request."""

    id: int
    origin: tuple[float, float]
    destination: tuple[float, float]
    release_time: float = 0.0
    demand: int = 1
    max_ride_time: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Request:
        return cls(
            id=data["id"],
            origin=tuple(data["origin"]),
            destination=tuple(data["destination"]),
            release_time=data.get("release_time", 0.0),
            demand=data.get("demand", 1),
            max_ride_time=data.get("max_ride_time"),
        )


@dataclass
class Vehicle:
    """Fleet-level parameters, shared by every vehicle."""

    capacity: int = 4
    speed: float = 1.0  # distance units per time unit
    service_time: float = 2.0  # dwell time at every stop


@dataclass
class Instance:
    """A complete DDRP instance."""

    name: str
    side: float
    depot: tuple[float, float]
    n_vehicles: int
    vehicle: Vehicle = field(default_factory=Vehicle)
    requests: list[Request] = field(default_factory=list)
    horizon: float = 0.0
    seed: int = 0

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Instance:
        vehicle = Vehicle(**data.get("vehicle", {}))
        requests = [Request.from_dict(r) for r in data.get("requests", [])]
        return cls(
            name=data["name"],
            side=data["side"],
            depot=tuple(data["depot"]),
            n_vehicles=data["n_vehicles"],
            vehicle=vehicle,
            requests=requests,
            horizon=data.get("horizon", 0.0),
            seed=data.get("seed", 0),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Instance:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    # -- lookups ------------------------------------------------------------
    def request(self, request_id: int) -> Request:
        for r in self.requests:
            if r.id == request_id:
                return r
        raise KeyError(request_id)

    def stop_location(self, request_id: int, kind: str) -> tuple[float, float]:
        req = self.request(request_id)
        return req.origin if kind == "P" else req.destination


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def route_travel_distance(instance: Instance, route: list[tuple[int, str]]) -> float:
    """Total distance of a route, departing from and returning to the depot."""
    pos = instance.depot
    total = 0.0
    for request_id, kind in route:
        loc = instance.stop_location(request_id, kind)
        total += math.dist(pos, loc)
        pos = loc
    total += math.dist(pos, instance.depot)
    return total


def simulate_route(
    instance: Instance, route: list[tuple[int, str]]
) -> dict:
    """Simulate one route, returning distances, load violations and timing."""
    pos = instance.depot
    t = 0.0
    load = 0
    distance = 0.0
    wait = 0.0
    ride = 0.0
    load_violations = 0
    precedence_violations = 0
    pickup_time: dict[int, float] = {}
    picked_up: set[int] = set()
    delivered: set[int] = set()

    for request_id, kind in route:
        req = instance.request(request_id)
        loc = instance.stop_location(request_id, kind)
        leg = math.dist(pos, loc)
        distance += leg
        t += leg / instance.vehicle.speed

        if kind == "P":
            load += req.demand
            pickup_time[request_id] = t
            picked_up.add(request_id)
            wait += max(0.0, t - req.release_time)
        else:  # drop-off
            if request_id not in picked_up:
                precedence_violations += 1
            else:
                ride += t - pickup_time[request_id]
            load -= req.demand
            delivered.add(request_id)

        if load > instance.vehicle.capacity:
            load_violations += 1
        t += instance.vehicle.service_time
        pos = loc

    distance += math.dist(pos, instance.depot)
    return {
        "distance": distance,
        "wait": wait,
        "ride": ride,
        "load_violations": load_violations,
        "precedence_violations": precedence_violations,
        "delivered": delivered,
    }


def route_is_feasible(instance: Instance, route: list[tuple[int, str]]) -> bool:
    """A route is feasible when capacity and precedence are respected."""
    result = simulate_route(instance, route)
    return result["load_violations"] == 0 and result["precedence_violations"] == 0


def evaluate(instance: Instance, routes: list[list[tuple[int, str]]]) -> dict:
    """Evaluate a full plan and return the (minimised) ``cost`` plus diagnostics."""
    total_distance = total_wait = total_ride = 0.0
    load_violations = precedence_violations = 0
    delivered: set[int] = set()

    for route in routes:
        r = simulate_route(instance, route)
        total_distance += r["distance"]
        total_wait += r["wait"]
        total_ride += r["ride"]
        load_violations += r["load_violations"]
        precedence_violations += r["precedence_violations"]
        delivered |= r["delivered"]

    served = len(delivered & {req.id for req in instance.requests})
    unserved = len(instance.requests) - served
    violations = load_violations + precedence_violations

    cost = (
        total_distance
        + UNSERVED_PENALTY * unserved
        + WAIT_WEIGHT * total_wait
        + VIOLATION_PENALTY * violations
    )
    return {
        "cost": cost,
        "total_distance": total_distance,
        "total_wait": total_wait,
        "total_ride": total_ride,
        "served": served,
        "unserved": unserved,
        "violations": violations,
    }
