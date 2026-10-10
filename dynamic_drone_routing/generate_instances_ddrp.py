"""Instance generator for the DDRP --- the *given* part of the assignment.

Builds JSON **workdays** for the SimPy simulator. Each instance contains:

* the **depot** position;
* the **fleet specs** (number of drones, max payload ``Q``, max flight distance
  per battery, cruise speed, service time);
* **static orders** (known at ``t = 0``) and **dynamic orders** (revealed during
  the day at their ``release_time``);
* the **workday** horizon (480 minutes).

Physical feasibility is guaranteed by construction: every order is lighter than
the payload capacity and close enough to the depot for a round trip on a single
battery.

Two ready-made instances are provided:

* ``toy``  --- 3 drones and a handful of orders, to develop a policy;
* ``hard`` --- 6 drones and clustered, bursty demand, to stress-test it.

Run it with (from the repository root)::

    uv run python -m dynamic_drone_routing.generate_instances_ddrp --name all
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from dynamic_drone_routing.simulator_ddrp import Fleet, Instance, Order

DEFAULT_INSTANCES_DIR = Path(__file__).resolve().parent / "instances"
WORKDAY = 480.0  # minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sample_position(rng: np.random.Generator, radius: float,
                     centers: list[tuple[float, float]] | None) -> tuple[float, float]:
    """A random point within ``radius`` of the origin (optionally clustered)."""
    if centers:
        cx, cy = centers[int(rng.integers(len(centers)))]
        x, y = rng.normal(cx, 0.15 * radius), rng.normal(cy, 0.15 * radius)
        r = math.hypot(x, y)
        if r > radius:  # pull the outlier back inside the reachable disk
            x, y = x * radius / r, y * radius / r
    else:
        r = radius * math.sqrt(rng.random())
        angle = rng.uniform(0.0, 2.0 * math.pi)
        x, y = r * math.cos(angle), r * math.sin(angle)
    return float(x), float(y)


def _make_orders(
    rng: np.random.Generator,
    n_static: int,
    n_dynamic: int,
    radius: float,
    capacity: float,
    centers: list[tuple[float, float]] | None = None,
) -> list[Order]:
    orders: list[Order] = []
    order_id = 0
    for _ in range(n_static):
        x, y = _sample_position(rng, radius, centers)
        weight = float(rng.uniform(0.3 * capacity, capacity))
        orders.append(Order(id=order_id, x=x, y=y, weight=weight,
                            release_time=0.0, static=True))
        order_id += 1
    for _ in range(n_dynamic):
        x, y = _sample_position(rng, radius, centers)
        weight = float(rng.uniform(0.3 * capacity, capacity))
        release = float(rng.uniform(20.0, WORKDAY - 40.0))
        orders.append(Order(id=order_id, x=x, y=y, weight=weight,
                            release_time=release, static=False))
        order_id += 1
    return orders


def assert_feasible(instance: Instance) -> None:
    """Raise if any single order cannot be served on a fresh battery."""
    fleet = instance.fleet
    for order in instance.orders:
        if order.weight > fleet.capacity + 1e-9:
            raise ValueError(f"order {order.id} is heavier than the capacity Q")
        round_trip = 2.0 * math.dist(instance.depot, order.position)
        if round_trip > fleet.max_range + 1e-9:
            raise ValueError(f"order {order.id} is out of range (round trip {round_trip:.1f})")


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------
def toy_instance(seed: int = 0) -> Instance:
    """A small, unclustered workday: 3 drones, 8 static + 6 dynamic orders."""
    rng = np.random.default_rng(seed)
    fleet = Fleet(n_drones=3, capacity=3.0, max_range=40.0, speed=1.0, service_time=1.0)
    orders = _make_orders(rng, n_static=8, n_dynamic=6,
                          radius=0.45 * fleet.max_range, capacity=fleet.capacity)
    instance = Instance(name="toy", depot=(0.0, 0.0), fleet=fleet,
                        workday=WORKDAY, orders=orders, seed=seed)
    assert_feasible(instance)
    return instance


def hard_instance(seed: int = 0) -> Instance:
    """A clustered, bursty workday: 6 drones, 20 static + 25 dynamic orders."""
    rng = np.random.default_rng(seed)
    fleet = Fleet(n_drones=6, capacity=2.5, max_range=34.0, speed=1.2, service_time=0.8)
    radius = 0.45 * fleet.max_range
    centers = [
        (0.6 * radius, 0.0),
        (-0.5 * radius, 0.5 * radius),
        (0.0, -0.7 * radius),
        (-0.4 * radius, -0.5 * radius),
    ]
    orders = _make_orders(rng, n_static=20, n_dynamic=25,
                          radius=radius, capacity=fleet.capacity, centers=centers)
    instance = Instance(name="hard", depot=(0.0, 0.0), fleet=fleet,
                        workday=WORKDAY, orders=orders, seed=seed)
    assert_feasible(instance)
    return instance


BUILDERS = {"toy": toy_instance, "hard": hard_instance}


def build(name: str, seed: int = 0) -> Instance:
    if name not in BUILDERS:
        raise ValueError(f"unknown instance '{name}' (choose from {sorted(BUILDERS)})")
    return BUILDERS[name](seed=seed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate DDRP workdays (JSON).")
    parser.add_argument("--name", choices=[*sorted(BUILDERS), "all"], default="all")
    parser.add_argument("--seed", type=int, default=0, help="random seed stored in the instance")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_INSTANCES_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> list[Path]:
    args = parse_args(argv)
    names = list(BUILDERS) if args.name == "all" else [args.name]
    written: list[Path] = []
    for name in names:
        instance = build(name, seed=args.seed)
        out = instance.save(args.out_dir / f"{name}.json")
        written.append(out)
        print(
            f"Wrote '{name}': {instance.fleet.n_drones} drones, "
            f"Q={instance.fleet.capacity} kg, range={instance.fleet.max_range}, "
            f"{len(instance.static_orders)} static + {len(instance.dynamic_orders)} dynamic "
            f"orders -> {out}"
        )
    return written


if __name__ == "__main__":
    main()
